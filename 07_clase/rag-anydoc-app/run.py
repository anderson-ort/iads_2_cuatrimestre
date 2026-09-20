import sys
from streamlit.web.cli import main

def start():
    sys.argv = ["streamlit", "run", "app.py"]
    main()

if __name__ == "__main__":
    start()