#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <thread>
#include <chrono>
#include <optional>
#include <atomic>

namespace zeroconf {

// ============================================================================
// ServiceInfo - Represents a discovered ZeroconfAI service
// ============================================================================
// This is like a Python dataclass or named tuple
struct ServiceInfo {
    std::string name;          
    std::string address;       
    int port;                  
    std::string url;           // Full URL (constructed from address:port)
    int priority;              // Lower = higher priority (mDNS convention)
    std::chrono::system_clock::time_point last_seen;  // Like Python's datetime
    bool is_healthy;           // Health check status
    
    // Constructor - similar to Python's __init__
    ServiceInfo(const std::string& name, const std::string& addr, int p, int prio = 50)
        : name(name), address(addr), port(p), priority(prio), 
          last_seen(std::chrono::system_clock::now()), is_healthy(false) {
        url = "http://" + address + ":" + std::to_string(port);
    }
    
    // Comparison operator for sorting - like Python's __lt__
    bool operator<(const ServiceInfo& other) const {
        return priority < other.priority;
    }
};

// ============================================================================
// ServiceDiscovery - Discovers and tracks ZeroconfAI services via mDNS
// ============================================================================
class ServiceDiscovery {
public:
    ServiceDiscovery();
    ~ServiceDiscovery();
    
    void start();
    void stop();
    
    // Get all healthy services, sorted by priority
    std::vector<ServiceInfo> get_services() const;
    
    // Get best (highest priority) healthy service
    std::optional<ServiceInfo> get_best_service() const;
    
private:
    void discovery_loop();
    void health_check_loop();
    bool check_health(const std::string& url);
    
    // Thread-safe storage - like threading.Lock() in Python
    mutable std::mutex services_mutex_;
    std::map<std::string, ServiceInfo> services_;
    
    // Background threads
    std::thread discovery_thread_;
    std::thread health_thread_;
    std::atomic<bool> running_;  // Thread-safe bool
};

// ============================================================================
// ProxyConfig - Configuration for the proxy server
// ============================================================================
struct ProxyConfig {
    std::string host = "0.0.0.0";
    int port = 8080;
    bool enable_cors = true;
    bool verbose = false;
};

// ============================================================================
// ProxyServer - The main reverse proxy server
// ============================================================================
class ProxyServer {
public:
    explicit ProxyServer(const ProxyConfig& config);
    ~ProxyServer();
    
    void start();
    void stop();
    bool is_running() const { return running_.load(); }
    
private:
    ProxyConfig config_;
    std::shared_ptr<ServiceDiscovery> discovery_;  // Like Python's shared reference
    std::atomic<bool> running_;
    std::thread server_thread_;
    
    void run_server();
};

} // namespace zeroconf