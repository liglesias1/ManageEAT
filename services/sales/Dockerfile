# Image of the sales service. Built from this folder only (the build context), so it cannot see the
# other service, the .env file or anything else in the repository.
#
#   docker build -t manageeat-sales --build-arg GIT_SHA=$(git rev-parse --short HEAD) services/sales
#
# Debian (not Alpine): the pymssql wheels need glibc 2.28 or newer, which Alpine's musl does not provide.
FROM python:3.12-slim-bookworm

# No .pyc files in the image, logs straight to stdout, no pip cache or version check
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer is reused while requirements.txt and constraints.txt do not change,
# so editing the code does not reinstall everything
COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

# Only the code the service runs, listed one by one (no COPY . .): tests, caches and secrets stay out
COPY app.py auth.py config.py database.py migrations.py observability.py ./
COPY domain/ domain/
COPY migrations/ migrations/

# The commit the image is built from, reported by GET /health as "version"
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

# Run as an unprivileged user: the code only reads its files, so root is never needed
RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
CMD ["python", "app.py"]