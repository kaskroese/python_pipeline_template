FROM python:3.9-slim-buster

WORKDIR /app

# Install pipenv
RUN pip install --upgrade pip && \
    pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies using pipenv
RUN pipenv install --system --deploy --ignore-pipfile

# Copy the current directory contents into the container at /app
COPY . .

# Create data directories that the pipeline will use
RUN mkdir -p data/raw data/processed data/output

CMD ["python", "main.py"]