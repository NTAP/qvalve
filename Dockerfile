FROM alpine:latest
RUN apk add --no-cache python3
ADD /bin /qvalve
EXPOSE 4433/UDP
CMD ["/qvalve/qvalve.py"]
