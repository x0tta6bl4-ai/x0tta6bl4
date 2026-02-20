APP_NAME := x0t-agent
VERSION := 0.1.0
BUILD_DIR := bin
LDFLAGS := -ldflags="-s -w -X main.Version=$(VERSION)"
GO := $(HOME)/go-sdk/go/bin/go

.PHONY: all build test clean

all: build

build:
	$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/$(APP_NAME) .

build-linux-amd64:
	GOOS=linux GOARCH=amd64 $(GO) build $(LDFLAGS) -o $(BUILD_DIR)/$(APP_NAME)-linux-amd64 .

build-linux-arm64:
	GOOS=linux GOARCH=arm64 $(GO) build $(LDFLAGS) -o $(BUILD_DIR)/$(APP_NAME)-linux-arm64 .

build-linux-armv7:
	GOOS=linux GOARCH=arm GOARM=7 $(GO) build $(LDFLAGS) -o $(BUILD_DIR)/$(APP_NAME)-linux-armv7 .

build-all: build-linux-amd64 build-linux-arm64 build-linux-armv7

test:
	$(GO) test ./... -v -race -count=1

test-cover:
	$(GO) test ./... -coverprofile=coverage.out
	$(GO) tool cover -func=coverage.out

clean:
	rm -rf $(BUILD_DIR) coverage.out

deps:
	$(GO) mod tidy
	$(GO) mod download
