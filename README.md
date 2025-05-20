# Dental Appointment USSD Application

This is a starter project for **Part 4 of Build Your Own USSD App with Open-Source Power**, a tutorial series for building USSD applications. The `dental_ussd` project provides a foundation for creating a USSD-based application for dental services using Python.

Before proceeding, ensure you have the latest version of python installed, this starter has been set up with python 3.12.3
For virtual environment, I am using `venv`.

To install venv

Linux
```Ubuntu
sudo apt update
sudo apt instal python3-venv
```
On Windows
`venv` is included with Python 3.3+ by default, so no separate installation is needed. Verify Python is installed:

```powershell
python --version
```


# Setup Instructions
1.  **Clone Repository**:
    ```bash
    git clone https://github.com/jayskar/dental_ussd.git
    ```
2.  **Navigate to the Project Directory** (`dental_ussd`).
    ```bash
    cd dental_ussd
    ```
3.  **Create a Virtual Environment**: Use Python's built-in venv module to create a virtual environment:
    ```bash
    python3 -m venv venv
    ```
4.  **Activate the Virtual environment**
    * On Linux
        ```bash
        source venv/bin/activate
        ```
    * On Windows
        ```bash
        venv\Scripts\activate
        ```
5.  **Install Dependencies**: Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
