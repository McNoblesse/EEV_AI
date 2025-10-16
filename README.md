# EEV-AI-Restructured

A modern AI-powered application built with FastAPI and Python.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd eeV-AI-Restructured
```

2. Create and activate a virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Navigate to the app directory:
```bash
cd app
```

2. Start the FastAPI development server:
```bash
uvicorn main:app --reload
```

3. The application will be available at:
   - API: http://localhost:8000
   - Interactive API documentation: http://localhost:8000/docs
   - Alternative API documentation: http://localhost:8000/redoc

## Project Structure

```
eeV-AI-Restructured/
├── .ipynb_checkpoints/
├── app/                 # Main application directory
│   └── main.py         # FastAPI application entry point
├── venv/               # Virtual environment (not tracked in git)
├── .env                # Environment variables
├── .gitignore          # Git ignore rules
└── requirements.txt    # Python dependencies
```

## Development

The application runs in reload mode by default, which means any changes to the code will automatically restart the server.

## Dependencies

Key dependencies include:
- **FastAPI (4.15.0)**: Modern web framework for building APIs
- **Uvicorn (0.37.0)**: ASGI server for running FastAPI
- **Unstructured (0.18.15)**: Document processing and parsing
- **LangChain & related packages**: AI/ML integration
- And more (see requirements.txt for full list)

## Stopping the Application

Press `Ctrl + C` in the terminal to stop the development server.

## Notes

- Make sure your virtual environment is activated before running the application
- The `--reload` flag enables auto-reload during development
- Check the `.env` file for any required environment variables

## Troubleshooting

If you encounter any issues:

1. Ensure all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Verify you're in the correct directory (`app/`) when running uvicorn

3. Check that port 8000 is not already in use by another application

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
