IMAGE    ?= ghcr.io/brk3/ogma
TAG      ?= $(shell git describe --tags --always --dirty)
PLATFORM ?= linux/amd64

.PHONY: venv test build push release digest clean

venv:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt

test:
	.venv/bin/python -m pytest -q

build:
	docker build --platform $(PLATFORM) -t $(IMAGE):$(TAG) .
	@got=$$(docker image inspect --format '{{.Os}}/{{.Architecture}}' $(IMAGE):$(TAG)); \
	  [ "$$got" = "$(PLATFORM)" ] || { echo "ERROR: built $$got, wanted $(PLATFORM)"; exit 1; }
	@echo "built $(IMAGE):$(TAG) for $(PLATFORM)"

push: build
	docker push $(IMAGE):$(TAG)
	@$(MAKE) --no-print-directory digest

digest:
	@docker image inspect --format '{{index .RepoDigests 0}}' $(IMAGE):$(TAG)

release: test push
	@echo "Flux picks up $(TAG) within the hour, or: flux reconcile image repository ogma -n flux-system"

clean:
	rm -rf .venv .pytest_cache __pycache__
