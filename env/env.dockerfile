FROM docker.io/library/ubuntu:24.04
WORKDIR /
ENV TZ=America/Vancouver
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ >/etc/timezone
RUN apt-get update && \
    apt-get -y install \
        git curl wget make nano ffmpeg unzip \
        libsm6 libxext6 \
        libegl1 libosmesa6 libegl-mesa0 libglx-mesa0 libgl1-mesa-dri \
        mesa-common-dev libegl1-mesa-dev && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x /Miniconda3-latest-Linux-x86_64.sh && \
    /Miniconda3-latest-Linux-x86_64.sh -b -p /miniconda3 && \
    rm -rf /Miniconda3-latest-Linux-x86_64.sh && \
    /miniconda3/bin/conda init bash && \
    chmod -R 777 /miniconda3
RUN export PATH="/miniconda3/bin:$PATH" && conda config --set auto_activate_base false
COPY ./env /env
WORKDIR /
ENV ENV_FOLDER=/env
SHELL ["/bin/bash", "-c"] 
RUN export PATH="/miniconda3/bin:$PATH" && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    bash ${ENV_FOLDER}/install_env.sh && \
    rm -rf /root/.cache/*

