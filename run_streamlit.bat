@echo off

:: Activate the Conda environment
::call conda activate base

:: Run the script
streamlit run app.py --server.port 8080
:: Open the URL in the default browser
start http://localhost:8501


###Daily bed occupation, and wait plots.