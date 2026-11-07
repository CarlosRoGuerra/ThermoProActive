# Imagem do serviço de backup do ThermoProActive.
# Base = postgres:16-alpine (mesma major do banco => pg_dump/pg_restore compatíveis)
# + gnupg (criptografia simétrica AES-256), rclone (envio a QUALQUER destino:
# S3-compatível, SFTP, B2, Google Drive, WebDAV...), curl (alerta opcional) e tzdata.
# Tudo open-source; nenhum provedor é obrigatório (Cláusula 12.4).
FROM postgres:16-alpine

RUN apk add --no-cache gnupg rclone curl tzdata tar

COPY common.sh backup.sh restore.sh agendar.sh healthcheck.sh /backup/
RUN chmod 0755 /backup/*.sh

# O ENTRYPOINT da imagem do postgres sobe um servidor; aqui só queremos os clientes.
ENTRYPOINT []
CMD ["/backup/agendar.sh"]
