# Project Standards for VAST Configuration Advisor

## Development Environment
- Always use Python virtual environments (venv) for isolation of dependencies
- Use `requirements.txt` to track dependencies
- Document all environment setup steps

## Port Configuration
- **IMPORTANT: Never use port 5000 for testing or development**
  - Port 5000 conflicts with macOS AirPlay and other system services
- **Avoid port 5050 if possible**
  - Port 5050 may be in use by other services on some systems
  - Use port 5060 for Flask development servers
  - For Docker containers, expose and map to port 5060

## Code Quality
- Follow PEP 8 style guidelines for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Break down complex functions to reduce cognitive complexity
- Use type hints where appropriate

## Testing
- Write unit tests for all calculation functions
- Test edge cases and boundary conditions
- Verify API endpoints with integration tests
- Test Docker containers locally before deployment

## Deployment
- Use Docker for containerization
- Configure applications for DigitalOcean App Platform
- Set appropriate environment variables for production
- Use gunicorn for production WSGI server
- Implement proper logging for production environments

## Security
- Never commit sensitive credentials to Git
- Use environment variables for configuration
- Validate all user inputs
- Implement appropriate error handling
- Follow OWASP security guidelines

## Documentation
- Maintain up-to-date README.md
- Document API endpoints
- Include setup and deployment instructions
- Document known issues and limitations
