FROM ubuntu:22.04

RUN apt-get update && apt-get upgrade -y
# RUN apt remove ethz-tsm-api ethz-tsm-ba ethz-tsm-crypt ethz-tsm-ssl
RUN echo "deb [arch=amd64] https://sp-repo.ethz.ch/apt/ stable main" > /etc/apt/sources.list.d/sp-repo.list
RUN cat /etc/apt/sources.list.d/sp-repo.list

RUN apt install curl gpg -y

RUN curl -s https://sp-repo.ethz.ch/sp-repo.gpg | gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/sp-repo.gpg --import

RUN chmod 666 /etc/apt/trusted.gpg.d/sp-repo.gpg
RUN apt update -y
RUN apt install gskcrypt64 gskssl64 tivsm-api64 tivsm-ba
RUN ldconfig /usr/lib64

# Copy persistent certificates and config files
# useful for debugging the client connection
# COPY --from=storage-client --chown=${UID}:${GID} dsm.opt /opt/tivoli/tsm/client/ba/bin/dsm.opt
# COPY --from=storage-client --chown=${UID}:${GID} dsm.sys /opt/tivoli/tsm/client/ba/bin/dsm.sys
# COPY --from=storage-client --chown=${UID}:${GID} dsmcert /opt/tivoli/tsm/client/ba/bin/dsmcert
# COPY --from=storage-client --chown=${UID}:${GID} dsmcert.idx /opt/tivoli/tsm/client/ba/bin/dsmcert.idx
# COPY --from=storage-client --chown=${UID}:${GID} dsmcert.kdb /opt/tivoli/tsm/client/ba/bin/dsmcert.kdb
# COPY --from=storage-client --chown=${UID}:${GID} dsmcert.sth /opt/tivoli/tsm/client/ba/bin/dsmcert.sth
# COPY --from=storage-client --chown=${UID}:${GID} adsm/. /etc/adsm/


WORKDIR /opt
