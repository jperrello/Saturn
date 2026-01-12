#include "local_proxy_client.hpp"
#include <iostream>
#include <csignal>
#include <memory>

// Global pointer for signal handling
std::unique_ptr<zeroconf::ProxyServer> g_server;

// Signal handler for graceful shutdown (Ctrl+C)
void signal_handler(int signal) {
    std::cout << "\n[Main] Received shutdown signal..." << std::endl;
    if (g_server) {
        g_server->stop();
    }
    exit(0);
}

int main(int argc, char* argv[]) {
    std::cout << "========================================" << std::endl;
    std::cout << "  ZeroconfAI Reverse Proxy" << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << std::endl;
    
    // Set up signal handler for Ctrl+C
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);
    
    // Configure the proxy
    zeroconf::ProxyConfig config;
    config.host = "127.0.0.1";  // Localhost only (change to 0.0.0.0 for network access)
    config.port = 8080;         // Different from Jan's 1337
    config.enable_cors = true;
    config.verbose = true;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "--port" && i + 1 < argc) {
            config.port = std::stoi(argv[++i]);
        }
        else if (arg == "--host" && i + 1 < argc) {
            config.host = argv[++i];
        }
        else if (arg == "--quiet") {
            config.verbose = false;
        }
        else if (arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [options]" << std::endl;
            std::cout << "Options:" << std::endl;
            std::cout << "  --port <port>    Proxy listen port (default: 8080)" << std::endl;
            std::cout << "  --host <host>    Proxy listen host (default: 127.0.0.1)" << std::endl;
            std::cout << "  --quiet          Disable verbose logging" << std::endl;
            std::cout << "  --help           Show this help message" << std::endl;
            std::cout << std::endl;
            std::cout << "Configure Jan to use: http://" << config.host 
                     << ":" << config.port << "/v1" << std::endl;
            return 0;
        }
    }
    
    // Create and start the proxy server
    try {
        g_server = std::make_unique<zeroconf::ProxyServer>(config);
        
        std::cout << "[Main] Starting proxy server..." << std::endl;
        std::cout << "[Main] Configure Jan to connect to: http://" 
                 << config.host << ":" << config.port << "/v1" << std::endl;
        std::cout << "[Main] Press Ctrl+C to stop" << std::endl;
        std::cout << std::endl;
        
        g_server->start();
        
        // Keep the main thread alive
        // The server runs in its own thread
        while (g_server->is_running()) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
        
    } catch (const std::exception& e) {
        std::cerr << "[Main] Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}