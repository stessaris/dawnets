# DAWNets Experiments

This directory includes the description of the experiments carried out for the publication of the article [Verification of data-aware workflows via reachability: formalisation and experiments](). The reader is referred to that publication for the details on the selected datasets for the experiments.

To reproduce the experiments it's sufficient to run the command `dawnets run <file>.yaml` where `<file>` is one of the following descriptions of a specific set of runs:

- `syntetic_coala-clingo`: synthetic models solved using *Coala*
- `syntetic_nusmv`: synthetic models solved using *nuXmv*
- `syntetic_pddl`: synthetic models solved using *fast downward*
- `bpichallenge-noise20-full-coala-clingo-json`: model learned from a dataset of process traces
- `bpichallenge-noise20-full-nusmv-json`: 
- `bpichallenge-noise20-full-pddl-json`: 
- `bpichallenge-noise20-nodata-coala-clingo-json`: as above but data is not taken into account
- `bpichallenge-noise20-nodata-nusmv-json`: 
- `bpichallenge-noise20-nodata-pddl-json`: 
- `bpichallenge-noise20-restricted-coala-clingo-json`: as above, where the domain of the variables is restricted to the values appearing in the model
- `bpichallenge-noise20-restricted-nusmv-json`: 
- `bpichallenge-noise20-restricted-pddl-json`: 

E.g.:

``` bash
$ dawnets run syntetic_pddl.yaml
```

After the completion of the experiment in the same directory it'll be created a `results` subdirectory where the results of the experiments will be included in a directory named with the timestamp of the starting time of the experiment, e.g:

```
results
└── 20190626T132607Z
    ├── bpichallenge_n20-t00000207_c025
    │   └── dawnets_coala_rvHPH0
    ├── bpichallenge_n20-t00000207_c050
    │   └── dawnets_coala_Aq19um
    ├── bpichallenge_n20-t00000207_c075
    │   └── dawnets_coala_dSIPsg
    ├── bpichallenge_n20-t00000207_c100
    │   └── dawnets_coala_32TG7P
    ....
    └── stats
        ├── bpichallenge_n20-t00000207_c025_coala.json
        ├── bpichallenge_n20-t00000207_c050_coala.json
        ├── bpichallenge_n20-t00000207_c075_coala.json
        ....
```

Each run has an unique *id* and the statistics (details of the execution and running time) are stored in JSON files within the `stats` directory.

