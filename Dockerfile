FROM alpine:latest
RUN apk add --no-cache python3
RUN pip3 install --upgrade pip
RUN pip3 install textX
ADD . /qvalve
EXPOSE 4433/UDP
CMD ["/qvalve/qvalve.py"]
