FROM golang:1.22-bullseye AS build
WORKDIR /app

# Cache dependencies first.
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source.
COPY . .

# Build the binary.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o server ./cmd/api

# Minimal runtime image with CA certs.
FROM gcr.io/distroless/base-debian12:nonroot
WORKDIR /app
COPY --from=build /app/server /app/server

ENV PORT=8080
EXPOSE 8080

USER nonroot
CMD ["/app/server"]

