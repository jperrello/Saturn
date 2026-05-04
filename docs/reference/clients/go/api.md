# Go client (`saturnd`)

`saturnd` is the Go reference implementation. Source: [`saturnd/`](https://github.com/jperrello/Saturn/tree/main/saturnd).

## Install

```bash
$ git clone https://github.com/jperrello/Saturn.git
$ cd Saturn/saturnd && go build -o saturnd ./cmd/saturnd
```

## Discover

```go
import "github.com/grandcat/zeroconf"

r, _ := zeroconf.NewResolver(nil)
ch := make(chan *zeroconf.ServiceEntry)
go r.Browse(ctx, "_saturn._tcp", "local.", ch)
for e := range ch {
    fmt.Printf("%s  prio=%s  %s:%d\n",
        e.Instance, txt(e.Text, "priority"), e.HostName, e.Port)
}
```

## Run as a discovery proxy

```bash
$ ./saturnd                                  # serves on :7827
$ curl http://localhost:7827/v1/agents       # JSON list of discovered Saturn instances
```

→ [Implementations overview](../../../implementations/index.md) · [TXT keys](../../protocol/txt-keys.md)
