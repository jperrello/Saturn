import argparse
import socket
from fastapi import FastAPI, HTTPException
import os
from zeroconf import ServiceInfo, Zeroconf
import uvicorn
import requests
import json
from pydantic import BaseModel
from typing import Literal
import aiohttp

#===================================
from dotenv import load_dotenv
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")

if not OPENROUTER_API_KEY or not OPENROUTER_BASE_URL:
    raise ValueError(
        "Missing environment variables. "
        "Please set OPENROUTER_API_KEY and OPENROUTER_BASE_URL in your .env file"
    )
#=======================================

description = "Zeroconf AI allows you to connect to llm services through your local network."
app = FastAPI(
    title="ZeroconfAI",
    description=description,
    summary="Get LLMs anywhere you go!",
    version="1.0",
    contact={
        "name": "Joey Perrello",
        "url": "https://jperrello.netlify.app/",
        "email": "jperrell@ucsc.edu",
    },
)

#====================================
# AI schemas

class CurrentChatContent(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class UserAIRequest(BaseModel):
    model: str
    messages: list[CurrentChatContent] # This is kind of a slippery slope, appending all the old messages into the context each time is a little spooky (memory leaks, context accumulation)
    max_tokens: int | None = None # Might be a better idea to set a default max later. Just dont know how much context is going to be dumped into this.




#========================================================
# App Routes
@app.get("/v1/health", description="Get's the health of server")
async def health() -> dict:
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def chat_completions(ai_request: UserAIRequest) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(OPENROUTER_BASE_URL, json=ai_request.model_dump(), headers=headers)

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )
    return response.json()

#Usually another route for models



#=========================================================
# Setting up the service

def register_zeroconfai(port: int) -> tuple[Zeroconf, ServiceInfo]:
    zeroconf = Zeroconf()

    host = socket.gethostname()
    host_ip = socket.gethostbyname(host)

    service_type = "_zeroconfai._tcp.local."
    service_name = f"Zeroconf.{service_type}" #person who sets up the service should be able to change this to whatever they want

    info = ServiceInfo(type_=service_type, name=service_name, port=port, addresses=[socket.inet_aton(host_ip)], server=f"{host}.local.", properties={'version': '1.0', 'api': 'OpenRouter'})

    zeroconf.register_service(info)

    print(f"{service_name} has been registered.")

    return zeroconf, info

# Port stuff
def is_port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            return True
    except OSError:
        return False

def find_port_number(start_port=8080, max_attempts=20) -> int:
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"There are no available ports in range {start_port} - {start_port + max_attempts}, please try again by specifying port number with --port.")



#=============================================

def main():

    parser = argparse.ArgumentParser(description="ZeroconfAI Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None, help="Specify the port you would like to connect to, or automatically find one by leaving blank.")
    parser.add_argument("--workers", type=int, default=3) #Ask: I am leaving workers in uvicorn to handle simultaneous requests. I think this is a better idea than adding httpx or aiohttp to this project. Maybe we can just have OpenRouter handle queing. 
    
    args = parser.parse_args()

    # conn_port will  be used to specify the port that is currently being used in the connection
    # we do this so that it isnt just called port (confusing), and also so we can run find_port_number
    if args.port == None:
        conn_port = find_port_number()
        print(f"Port number was not specified, found available port at {conn_port}")
    else:
        if is_port_available(args.port):
            conn_port = args.port
        else:
            print(f"Specified port {args.port} is currently in use, finding the next available port...")
            conn_port = find_port_number() # TODO: give users the option to automatically find a new port, or try again by specifying a different one.
            print(f"Found available port at {conn_port}")

    zeroconf, service_info = register_zeroconfai(conn_port)

    print(f"ZeroconfAi is starting at {args.host}:{conn_port}")
    print(f"Docs are found at http://localhost:{conn_port}/docs")

    try:       
        uvicorn.run(app, host=args.host, port = conn_port)
    finally:
        print(f"Unregistering ZeroconfAI services...")
        zeroconf.unregister_service(service_info)
        zeroconf.close()

        #now we can run python server.py --host 127.0.0.1 port 8081 and it will actually be configured properly
        #if you just run python server.py it just defaults to 0.0.0.0 and 8080



if __name__ == "__main__":

    main()
   