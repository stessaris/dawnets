# Synthetic Benchmarks

To build the benchmarks run

```
docker run --rm -v "`pwd`":/dawnets -w /dawnets dawnets run build-models.yaml
```

The models and traces will be written in `build/models_and_traces`, including the SVG of the corresponding model. Details of the runs will be written in the corresponding timestamped directory in `build`.

For each pattern (M1-M5) and trace the generated files are:

```
M1_dawnet_1.svg
M1_dawnet_1.yaml
M1_dawnet_1-t3_all-trace.yaml
M1_dawnet_1-t3_c25-trace.yaml
M1_dawnet_1-t3_c50-trace.yaml
M1_dawnet_1-t3_c75-trace.yaml
```