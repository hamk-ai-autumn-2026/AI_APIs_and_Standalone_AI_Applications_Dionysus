The provided source, `big_report.txt`, details the functionality and design of a Python command-line tool named `llm_sources.py`, which is intended for processing various document types (text, HTML, CSV, DOCX, PDF) and interacting with OpenAI-compatible LLM APIs. Here’s a summary of the key points:

### Key Features
- **Installation Requirements**: The tool requires Python 3.9+ and specific libraries such as `requests`, `beautifulsoup4`, `PyMuPDF`, and `python-docx`.
- **Functionality**: It converts documents into labeled plain text for analysis, supports multiple sources in one command, and allows users to customize queries and output formats.
- **Command-Line Usage**: Users can summarize documents, handle multiple sources, and specify various command-line flags for queries, output options, verbosity, and model selection.
- **Source Handling**: The tool employs different methods for reading various file types, ensuring compatibility and proper extraction of content.
- **Error Handling**: It includes robust mechanisms for managing errors related to unsupported formats, HTTP issues, and API failures, with clear exit codes and user feedback.

### Security Measures
- **Content Sanitization**: The tool removes potentially harmful HTML elements to prevent prompt-injection attacks.
- **Fencing**: Each source is clearly marked to indicate it contains untrusted data.
- **System-Prompt Rules**: Instructions must come solely from the system prompt and user queries, ensuring that any prompt-injection attempts are ignored.

### Additional Features
- **Chunking and Token Management**: The tool implements strategies for managing large documents, including a map-reduce approach for summarization and a context-window policy to limit text size sent to the API.
- **Testing Utilities**: It includes offline unit tests and a mock server for simulating API interactions, allowing users to test the tool without needing an actual API key.

### Overall Purpose
The `llm_sources.py` tool is designed primarily for educational purposes and document analysis, emphasizing flexibility, security, and ease of use. It is not intended for production-level applications but serves as a prototype for interacting with LLMs in a document processing context.
