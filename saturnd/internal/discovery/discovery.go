package discovery

import (
	"context"
	"log"
	"strconv"
	"time"

	"github.com/grandcat/zeroconf"
)

type Service struct {
	Name       string
	Host       string
	Port       int
	Priority   int
	Properties map[string]string
}

type Discovery struct {
	serviceType string
	domain      string
	services    map[string]Service
}

func New(serviceType, domain string) *Discovery {
	return &Discovery{
		serviceType: serviceType,
		domain:      domain,
		services:    make(map[string]Service),
	}
}

func (d *Discovery) Run(ctx context.Context, onDiscover func(Service)) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			d.browse(ctx, onDiscover)
		}
	}
}

func (d *Discovery) browse(ctx context.Context, onDiscover func(Service)) {
	resolver, err := zeroconf.NewResolver(nil)
	if err != nil {
		log.Printf("Failed to create resolver: %v", err)
		return
	}

	entries := make(chan *zeroconf.ServiceEntry)

	browseCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	go func() {
		for entry := range entries {
			props := make(map[string]string)
			for _, txt := range entry.Text {
				// Parse "key=value" format
				for i := 0; i < len(txt); i++ {
					if txt[i] == '=' {
						props[txt[:i]] = txt[i+1:]
						break
					}
				}
			}

			priority := 100
			if p, ok := props["priority"]; ok {
				if parsed, err := strconv.Atoi(p); err == nil {
					priority = parsed
				}
			}

			svc := Service{
				Name:       entry.Instance,
				Host:       entry.HostName,
				Port:       entry.Port,
				Priority:   priority,
				Properties: props,
			}

			// Check if this is new or updated
			existing, exists := d.services[svc.Name]
			if !exists || existing.Properties["ephemeral_key"] != svc.Properties["ephemeral_key"] {
				d.services[svc.Name] = svc
				onDiscover(svc)
			}
		}
	}()

	err = resolver.Browse(browseCtx, d.serviceType, d.domain, entries)
	if err != nil {
		log.Printf("Browse error: %v", err)
	}

	<-browseCtx.Done()
}

func (d *Discovery) GetServices() []Service {
	result := make([]Service, 0, len(d.services))
	for _, svc := range d.services {
		result = append(result, svc)
	}
	return result
}

func (d *Discovery) GetServiceByName(name string) (Service, bool) {
	svc, ok := d.services[name]
	return svc, ok
}
