FROM continuumio/miniconda as build-fd
# see <https://hub.docker.com/r/continuumio/miniconda/>
# based on Python 2.7

RUN apt-get update && apt-get install -y \
    bison \
    build-essential \
    cmake \
    curl \
    flex \
    git \
  &&  apt-get clean \
  && rm -rf /var/lib/apt/lists

ENV SRC_DIR=/usr/local/src

WORKDIR ${SRC_DIR}/fd

# Fetch FD
# RUN hg clone http://hg.fast-downward.org fd
# make sure to use GNU tar
RUN curl -SL https://github.com/danfis/fast-downward-mirror/archive/0c2e5cba9c0a0e3ff237d41e2e0b2c45b6f6b508.tar.gz \
    | tar -xz --strip-components 1

RUN python build.py release

WORKDIR ${SRC_DIR}/VAL

# Fetch VAL
# RUN git clone https://github.com/KCL-Planning/VAL.git
RUN curl -SL https://github.com/KCL-Planning/VAL/archive/a5565396007eee73ac36527fbf904142b3077c74.tar.gz \
    | tar -xz --strip-components 1

RUN make

#############################################
# Final image
#############################################
FROM continuumio/miniconda

RUN apt-get update && apt-get install -y --no-install-recommends \
    collectl \
    curl \
    procps \
    psmisc \
  &&  apt-get clean \
  && rm -rf /var/lib/apt/lists

ENV SRC_DIR=/usr/local/src

#############################################
# Copy FD executables from build stage
#############################################

WORKDIR ${SRC_DIR}

COPY --from=build-fd ${SRC_DIR}/fd ${SRC_DIR}/fd
COPY --from=build-fd ${SRC_DIR}/VAL/validate /usr/local/bin
RUN ln -s ${SRC_DIR}/fd/fast-downward.py /usr/local/bin/fast-downward ;\
    chmod a+x /usr/local/bin/validate

#############################################
# Install nuXsmv
#############################################

WORKDIR ${SRC_DIR}/nuXmv

# Fetch nuXsmv binaries
RUN curl -SL https://es.fbk.eu/tools/nuxmv/downloads/nuXmv-1.1.1-linux64.tar.gz \
    | tar -xz --strip-components 1
RUN ln -s ${SRC_DIR}/nuXmv/bin/nuXmv /usr/local/bin/nuXmv

#############################################
# Install clingo and coala
#############################################

# Install Coala in a virtual environment
ENV COALA_ENV=coala

# Coala requires Py2
RUN conda create --quiet --yes -n ${COALA_ENV} python=2.7
RUN conda install --quiet --yes -n ${COALA_ENV} -c potassco/label/dev clingo


ENV COALA_GIT=git+https://github.com/potassco/coala.git@e561982c7ebd9af7c6252a3838c766465aaf220e#egg=coala

RUN /bin/bash -c "source activate ${COALA_ENV} ; pip install -e ${COALA_GIT} --src ${SRC_DIR}"

# Make coala available outside the environment
RUN for f in coala outputformatclingocoala clingo ; do \
        fpath="`/bin/bash -c \"source activate ${COALA_ENV}; which $f\"`" ; \
        [ -n "$fpath" ] && ln -s "$fpath" /usr/local/bin ; \
    done

COPY coala-clingo /usr/local/bin
RUN chmod a+x /usr/local/bin/coala-clingo

#############################################
# Install DAWNets
#############################################

# install psutil from conda to avoid compilation (no Linux wheels in PyPI)
RUN conda install -c anaconda psutil graphviz

COPY . ${SRC_DIR}/dawnets/
# COPY doesn't parse variables
#   see <https://github.com/moby/moby/issues/35018>


WORKDIR ${SRC_DIR}/dawnets

RUN pip install .

#############################################
# Entrypoint and home folder
#############################################

ENTRYPOINT ["dawnets"]
CMD ["--help"]