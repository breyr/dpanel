FROM --platform=$BUILDPLATFORM golang:latest as builder

ARG TARGETARCH

WORKDIR /app
COPY * /app/
RUN CGO_ENABLED=0 GOOS=linux GOARCH=$TARGETARCH go build -a -o output/main main.go

FROM alpine:latest
WORKDIR /root
COPY --from=builder /app/output/main .
CMD ["./main"]
