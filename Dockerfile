FROM python:3.9-buster

# Install development tools and libraries
# RUN apt-get update && apt-get install -y build-essential libopenblas-dev liblapack-dev

# ENV FLASK_APP=application.py 
# ENV FLASK_RUN_HOST=0.0.0.0

WORKDIR /application
COPY . /application 

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# EXPOSE 5000
EXPOSE $PORT

#For Heroku
CMD streamlit run application.py

# CMD python application.py
# CMD ["flask","run"]