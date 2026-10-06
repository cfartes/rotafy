FROM restic/restic:0.19.1 AS restic
FROM postgres:17-alpine
COPY --from=restic /usr/bin/restic /usr/local/bin/restic
COPY backup.sh /usr/local/bin/rotafy-backup
RUN chmod 755 /usr/local/bin/rotafy-backup
ENTRYPOINT ["/usr/local/bin/rotafy-backup"]
