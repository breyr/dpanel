FROM golang:latest

WORKDIR /app

COPY . .

RUN go mod tidy && go build -o main .

CMD ["./main"]
