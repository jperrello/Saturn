#include "local_proxy_client.hpp"
#include <iostream>
#include <algorithm>
#include <sstream>

// Third-party libraries
#include <httplib.h>           // cpp-httplib for HTTP server (header-only)
#include <nlohmann/json.hpp>   // JSON library (header-only)
#include <curl/curl.h>         // libcurl for HTTP client

// Avahi (Linux) or dns_sd (macOS) for mDNS service discovery
#ifdef __APPLE__
    #include <dns_sd.h>
#else
    #include <avahi-client/client.h>
    #include <avahi-client/lookup.h>
    #include <avahi-common/simple-watch.h>
    #include <avahi-common/error.h>
#endif

using json = nlohmann::json;

namespace zeroconf {

// ============================================================================
// CURL Utilities - HTTP client for forwarding requests and health checks
// ============================================================================

// Callback for CURL to write response data
// In Python, requests library handles this automatically
static size_t curl_write_callback(void* contents, size_t size, size_t nmemb, std::string* output) {
    size_t total_size = size * nmemb;
    output->append(static_cast<char*>(contents), total_size);
    return total_size;
}

// Simple HTTP GET using libcurl - like requests.get() in Python
static std::pair<int, std::string> http_get(const std::string& url, int timeout_seconds = 5) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        return {500, "{\"error\": \"Failed to initialize HTTP client\"}"};
    }
    
    std::string response_body;
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, static_cast<long>(timeout_seconds));
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);  // Follow redirects
    
    CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_easy_cleanup(curl);
    
    if (res != CURLE_OK) {
        return {0, ""};  // Connection failed
    }
    
    return {static_cast<int>(http_code), response_body};
}

// Simple HTTP POST - like requests.post() in Python
static std::pair<int, std::string> http_post(const std::string& url, 
                                               const std::string& body,
                                               int timeout_seconds = 120) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        return {500, "{\"error\": \"Failed to initialize HTTP client\"}"};
    }
    
    std::string response_body;
    
    // Set headers - equivalent to requests.post(..., headers={...})
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, static_cast<long>(timeout_seconds));
    
    CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    if (res != CURLE_OK) {
        return {0, ""};
    }
    
    return {static_cast<int>(http_code), response_body};
}

// ============================================================================
// ServiceDiscovery Implementation
// ============================================================================

ServiceDiscovery::ServiceDiscovery() : running_(false) {
    // Initialize CURL globally - do this once per program
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

ServiceDiscovery::~ServiceDiscovery() {
    stop();
    curl_global_cleanup();
}

void ServiceDiscovery::start() {
    if (running_.load()) return;
    
    running_.store(true);
    
    // Spawn background threads
    // In Python: threading.Thread(target=self.discovery_loop).start()
    discovery_thread_ = std::thread(&ServiceDiscovery::discovery_loop, this);
    health_thread_ = std::thread(&ServiceDiscovery::health_check_loop, this);
    
    std::cout << "[Discovery] Started ZeroconfAI service discovery" << std::endl;
}

void ServiceDiscovery::stop() {
    if (!running_.load()) return;
    
    running_.store(false);
    
    // Wait for threads to finish - like thread.join() in Python
    if (discovery_thread_.joinable()) {
        discovery_thread_.join();
    }
    if (health_thread_.joinable()) {
        health_thread_.join();
    }
    
    std::cout << "[Discovery] Stopped service discovery" << std::endl;
}

void ServiceDiscovery::discovery_loop() {
    // This is where mDNS discovery happens
    // For now, we'll implement a simplified version that looks for known services
    
    std::cout << "[Discovery] Starting mDNS discovery for _zeroconfai._tcp" << std::endl;
    
    while (running_.load()) {
        // TODO: Replace with actual Avahi/Bonjour browse
        // For now, let's check for Ollama on localhost as a proof of concept
        
        // Check if Ollama is running (common ZeroconfAI-compatible service)
        auto [status, _] = http_get("http://localhost:11434/api/tags", 2);
        
        if (status == 200) {
            std::lock_guard<std::mutex> lock(services_mutex_);
            
            std::string service_name = "ollama-localhost";
            auto it = services_.find(service_name);
            
            if (it == services_.end()) {
                // New service discovered
                ServiceInfo info(service_name, "127.0.0.1", 11434, 10);
                services_[service_name] = info;
                std::cout << "[Discovery] Found service: " << service_name 
                         << " at " << info.url << std::endl;
            } else {
                // Update last_seen timestamp
                it->second.last_seen = std::chrono::system_clock::now();
            }
        }
        
        // Clean up stale services (not seen in 30 seconds)
        {
            std::lock_guard<std::mutex> lock(services_mutex_);
            auto now = std::chrono::system_clock::now();
            
            // C++ doesn't let you modify a map while iterating, so collect keys to remove
            std::vector<std::string> to_remove;
            
            for (const auto& [name, service] : services_) {
                auto age = std::chrono::duration_cast<std::chrono::seconds>(
                    now - service.last_seen
                ).count();
                
                if (age > 30) {
                    to_remove.push_back(name);
                }
            }
            
            for (const auto& name : to_remove) {
                std::cout << "[Discovery] Removing stale service: " << name << std::endl;
                services_.erase(name);
            }
        }
        
        // Sleep for 5 seconds between discovery attempts
        std::this_thread::sleep_for(std::chrono::seconds(5));
    }
}

void ServiceDiscovery::health_check_loop() {
    std::cout << "[Health] Starting health check loop" << std::endl;
    
    while (running_.load()) {
        // Get copy of services to check
        std::vector<ServiceInfo> services_to_check;
        {
            std::lock_guard<std::mutex> lock(services_mutex_);
            for (const auto& [name, service] : services_) {
                services_to_check.push_back(service);
            }
        }
        
        // Check health of each service
        for (const auto& service : services_to_check) {
            bool healthy = check_health(service.url);
            
            // Update health status
            std::lock_guard<std::mutex> lock(services_mutex_);
            auto it = services_.find(service.name);
            if (it != services_.end()) {
                bool was_healthy = it->second.is_healthy;
                it->second.is_healthy = healthy;
                
                if (healthy != was_healthy) {
                    std::cout << "[Health] " << service.name 
                             << " is now " << (healthy ? "healthy" : "unhealthy") << std::endl;
                }
            }
        }
        
        // Sleep for 10 seconds between health checks
        std::this_thread::sleep_for(std::chrono::seconds(10));
    }
}

bool ServiceDiscovery::check_health(const std::string& url) {
    // Try to hit the /api/tags endpoint (Ollama-style)
    // Most OpenAI-compatible services have either /v1/models or /api/tags
    auto [status, _] = http_get(url + "/api/tags", 3);
    
    if (status == 200) return true;
    
    // Try alternative health check endpoint
    auto [status2, __] = http_get(url + "/v1/models", 3);
    return (status2 == 200);
}

std::vector<ServiceInfo> ServiceDiscovery::get_services() const {
    std::lock_guard<std::mutex> lock(services_mutex_);
    
    std::vector<ServiceInfo> result;
    
    // Only return healthy services
    for (const auto& [name, service] : services_) {
        if (service.is_healthy) {
            result.push_back(service);
        }
    }
    
    // Sort by priority (lower number = higher priority)
    std::sort(result.begin(), result.end());
    
    return result;
}

std::optional<ServiceInfo> ServiceDiscovery::get_best_service() const {
    auto services = get_services();
    if (services.empty()) {
        return std::nullopt;  // Like returning None in Python
    }
    return services[0];  // First element (highest priority)
}

// ============================================================================
// ProxyServer Implementation
// ============================================================================

ProxyServer::ProxyServer(const ProxyConfig& config)
    : config_(config), running_(false) {
    
    discovery_ = std::make_shared<ServiceDiscovery>();
}

ProxyServer::~ProxyServer() {
    stop();
}

void ProxyServer::start() {
    if (running_.load()) return;
    
    // Start service discovery
    discovery_->start();
    
    // Give discovery a moment to find services
    std::cout << "[Proxy] Waiting for service discovery..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(2));
    
    running_.store(true);
    
    // Start the HTTP server in a separate thread
    server_thread_ = std::thread(&ProxyServer::run_server, this);
}

void ProxyServer::stop() {
    if (!running_.load()) return;
    
    running_.store(false);
    discovery_->stop();
    
    if (server_thread_.joinable()) {
        server_thread_.join();
    }
    
    std::cout << "[Proxy] Server stopped" << std::endl;
}

void ProxyServer::run_server() {
    // Create HTTP server using cpp-httplib
    // This is similar to Flask or FastAPI in Python
    httplib::Server server;
    
    // Enable CORS if requested
    if (config_.enable_cors) {
        server.set_default_headers({
            {"Access-Control-Allow-Origin", "*"},
            {"Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"},
            {"Access-Control-Allow-Headers", "Content-Type, Authorization"}
        });
    }
    
    // ========================================================================
    // Route: GET /v1/health
    // ========================================================================
    server.Get("/v1/health", [this](const httplib::Request& req, httplib::Response& res) {
        auto services = discovery_->get_services();
        
        json response = {
            {"status", services.empty() ? "no_services" : "ok"},
            {"provider", "ZeroconfAI Proxy"},
            {"services", services.size()}
        };
        
        res.set_content(response.dump(2), "application/json");
        res.status = services.empty() ? 503 : 200;
    });
    
    // ========================================================================
    // Route: GET /v1/models
    // ========================================================================
    server.Get("/v1/models", [this](const httplib::Request& req, httplib::Response& res) {
        auto services = discovery_->get_services();
        
        if (services.empty()) {
            json error = {{"error", "No ZeroconfAI services available"}};
            res.set_content(error.dump(), "application/json");
            res.status = 503;
            return;
        }
        
        // For simplicity, just forward to the best service
        auto best = discovery_->get_best_service();
        if (!best) {
            json error = {{"error", "No healthy services"}};
            res.set_content(error.dump(), "application/json");
            res.status = 503;
            return;
        }
        
        if (config_.verbose) {
            std::cout << "[Proxy] Fetching models from " << best->name << std::endl;
        }
        
        auto [status, body] = http_get(best->url + "/api/tags");
        
        if (status != 200) {
            json error = {{"error", "Failed to fetch models"}};
            res.set_content(error.dump(), "application/json");
            res.status = 502;
            return;
        }
        
        // Parse Ollama response and convert to OpenAI format
        try {
            auto ollama_response = json::parse(body);
            json openai_models = json::array();
            
            if (ollama_response.contains("models")) {
                for (const auto& model : ollama_response["models"]) {
                    std::string model_name = model.value("name", "unknown");
                    openai_models.push_back({
                        {"id", model_name},
                        {"object", "model"},
                        {"created", 0},
                        {"owned_by", "zeroconfai"}
                    });
                }
            }
            
            json response = {
                {"object", "list"},
                {"data", openai_models}
            };
            
            res.set_content(response.dump(2), "application/json");
            
        } catch (const std::exception& e) {
            json error = {{"error", std::string("Parse error: ") + e.what()}};
            res.set_content(error.dump(), "application/json");
            res.status = 500;
        }
    });
    
    // ========================================================================
    // Route: POST /v1/chat/completions
    // ========================================================================
    server.Post("/v1/chat/completions", [this](const httplib::Request& req, httplib::Response& res) {
        try {
            // Get the best service to route to
            auto target = discovery_->get_best_service();
            
            if (!target) {
                json error = {{"error", "No healthy ZeroconfAI services available"}};
                res.set_content(error.dump(), "application/json");
                res.status = 503;
                return;
            }
            
            if (config_.verbose) {
                std::cout << "[Proxy] Routing chat completion to " << target->name << std::endl;
            }
            
            // Parse incoming OpenAI request
            auto request_json = json::parse(req.body);
            
            // Convert OpenAI format to Ollama format
            json ollama_request = {
                {"model", request_json.value("model", "llama2")},
                {"messages", request_json["messages"]},
                {"stream", request_json.value("stream", false)}
            };
            
            // Forward to Ollama
            auto [status, body] = http_post(
                target->url + "/api/chat",
                ollama_request.dump()
            );
            
            if (status == 0 || status >= 500) {
                json error = {{"error", "Backend service unavailable"}};
                res.set_content(error.dump(), "application/json");
                res.status = 502;
                return;
            }
            
            // Convert Ollama response back to OpenAI format
            try {
                auto ollama_response = json::parse(body);
                
                json openai_response = {
                    {"id", "chatcmpl-zeroconfai"},
                    {"object", "chat.completion"},
                    {"created", std::time(nullptr)},
                    {"model", request_json.value("model", "unknown")},
                    {"choices", json::array({
                        {
                            {"index", 0},
                            {"message", ollama_response["message"]},
                            {"finish_reason", "stop"}
                        }
                    })},
                    {"usage", {
                        {"prompt_tokens", 0},
                        {"completion_tokens", 0},
                        {"total_tokens", 0}
                    }}
                };
                
                res.set_content(openai_response.dump(2), "application/json");
                res.status = 200;
                
            } catch (const std::exception& e) {
                // If conversion fails, just pass through the raw response
                res.set_content(body, "application/json");
                res.status = status;
            }
            
        } catch (const std::exception& e) {
            json error = {{"error", std::string("Proxy error: ") + e.what()}};
            res.set_content(error.dump(), "application/json");
            res.status = 500;
        }
    });
    
    // ========================================================================
    // Start the server
    // ========================================================================
    std::cout << "[Proxy] Starting server on " << config_.host << ":" << config_.port << std::endl;
    std::cout << "[Proxy] OpenAI-compatible API: http://" << config_.host << ":" 
              << config_.port << "/v1" << std::endl;
    std::cout << "[Proxy] Point Jan to this endpoint!" << std::endl;
    
    server.listen(config_.host, config_.port);
}

} // namespace zeroconf