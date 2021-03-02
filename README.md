# ocr-bank-statement

## Development

#### USE PYTHON 3 FOR THIS PROJECT

1. set-up project environment (e.g. Using virtualenv)

    ```virtualenv -p python3 venv```
    
    ```source venv/bin/activate```
    
    ```pip3 install -r requirements.txt```

2. run project in debug mode (Flask application)

    ```source venv/bin/activate```
    
    ```python3 run_debug.py```

## Deployment for Testing
This builds a docker image that runs a Flask application for debug/testing purposes.
1. Build debug docker image and save to .tar file

    ```docker build -f Dockerfile_debug -t bsocr-debug:{VERSION_INDICIATOR} .```

    ```docker save -o {VERSION_INDICATOR}_{DATE}_bsocr-debug.tar bsocr-debug:{VERSION_INDICIATOR}```

2. Run docker image
   ```docker run --name {NAME} -p {PORT_OUT}:5000 bsocr-debug:{VERSION_INDICATOR}```

## Deployment for SLP

1. Build docker image and save to .tar file

    ```docker build -t bsocr:{VERSION_INDICIATOR} .```

    ```docker save -o {VERSION_INDICATOR}_{DATE}_bsocr.tar bsocr:{VERSION_INDICIATOR}```

2. Copy docker image to server

    server credentials:
    ```
    IP: 10.59.99.42
    Username: wls81
    Password: wls81
    ```

3. Load and run docker image in SLP server

    ```docker load -i {VERSION_INDICATOR}_{DATE}_ocr-bank-statement.tar```
    
    ```docker run -ulimit nofile=256324:256324 -v {PATH_TO_MQ_CONFIGURATIONS_IN_SERVER}:/deploy/app/assets/mq_configurations registry.gammalab.sg/ocr-bank-state:{VERSION_INDICIATOR}```


### MQ Configuration for SLP DEV
```
listen-configuration:
  queue: SDP.SDP_TO_OCR_STATEMENT_REQUEST
  host: '10.59.99.13'
  port: 5672
  virtual_host: /
  username: slp
  password: paic1234
  routing_key: SDP_TO_OCR_STATEMENT_REQUEST
  exchange: SDP

publish-configuration:
  queue: OCR.OCR_TO_SDP_STATEMENT_RESPONSE
  host: '10.59.99.13'
  port: 5672
  virtual_host: /
  username: slp
  password: paic1234
  routing_key: OCR_TO_SDP_STATEMENT_RESPONSE
  exchange: OCR
```


### MQ Configuration for SLP STAGING
```
listen-configuration:
  queue: SDP.SDP_TO_OCR_STATEMENT_REQUEST
  host: '10.59.99.60'
  port: 5672
  virtual_host: /
  username: slp
  password: paic1234
  routing_key: SDP_TO_OCR_STATEMENT_REQUEST
  exchange: SDP

publish-configuration:
  queue: OCR.OCR_TO_SDP_STATEMENT_RESPONSE
  host: '10.59.99.60'
  port: 5672
  virtual_host: /
  username: slp
  password: paic1234
  routing_key: OCR_TO_SDP_STATEMENT_RESPONSE
  exchange: OCR
```

## Deployment for RHB
NOTE: RHB deployment is done by RHB. Docker image is built and delivered

1. Build docker image and save to .tar file

    ```docker build -t bank-statement-ocr:latest .```

    ```docker save -o bank_statement_{VERSION_INDICATOR}.tar bank_statement_ocr:latest```

2. Copy docker image to shared folder and notify Azrul @ RHB for deployment