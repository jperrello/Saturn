# Demo recordings

`saturn-demo.cast` — asciinema recording of `demo/run.sh` running
end-to-end on macOS. ~6.5 seconds (the model is warm in memory; cold
first run pulls ~400 MB and takes longer). Captures all six demo
steps and a real `/v1/chat/completions` JSON response.

## Play it

```sh
uvx asciinema play demo/recordings/saturn-demo.cast
```

## Re-record

```sh
uvx asciinema rec demo/recordings/saturn-demo.cast --overwrite \
  --command "bash demo/run.sh" \
  --title "Saturn 5-minute demo" \
  --idle-time-limit 1.5
```
