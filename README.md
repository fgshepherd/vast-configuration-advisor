# VAST Configuration Advisor

A Flask web application that calculates optimal VAST C-Box/D-Box configurations based on user-defined resource utilization targets.

## Overview

The VAST Configuration Advisor helps users determine the optimal hardware configuration for VAST storage systems based on their specific requirements for rack unit utilization and power consumption. It provides multiple optimized configurations prioritizing different performance metrics:

- Maximum Storage Capacity
- Maximum NFS Read Performance
- Maximum NFS Write Performance
- Maximum S3 Read Performance
- Maximum S3 Write Performance

Each configuration includes detailed metrics and a visual representation of the rack layout.

## Features

- **Constraint-Based Optimization**: Calculate configurations that meet user-defined rack unit and power constraints
- **Multiple Optimization Targets**: Find configurations optimized for different performance priorities
- **Visual Rack Layout**: See a visual representation of each configuration
- **Custom Component Graphics**: Upload custom images for C-Boxes, D-Boxes, switches, and rack backgrounds
- **Responsive Design**: Works on desktop and mobile devices
- **Docker Support**: Easy deployment with Docker

## Technology Stack

- **Backend**: Python with Flask
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Docker, Gunicorn
- **Target Platform**: DigitalOcean App Platform

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Docker (optional, for containerized deployment)

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/fgshepherd/vast-configuration-advisor.git
   cd vast-configuration-advisor
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Access the application at http://localhost:5060

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t vast-config-advisor .
   ```

2. Run the container:
   ```bash
   docker run -p 5060:5060 vast-config-advisor
   ```

3. Access the application at http://localhost:5060

## API Documentation

### Calculate Optimal Configurations

**Endpoint**: `/calculate`

**Method**: POST

**Request Body**:
```json
{
  "percentRU": 80,
  "percentPower": 70
}
```

**Response**:
```json
{
  "maxCapa": {
    "nc": 4,
    "nd": 8,
    "value": 1200,
    "metrics": {
      "capacity_tb": 1200,
      "nfs_read_gbps": 32,
      "nfs_write_gbps": 24,
      "s3_read_gbps": 28,
      "s3_write_gbps": 20,
      "total_ru": 16,
      "total_kw": 12.8
    }
  },
  "maxNfsRead": { ... },
  "maxNfsWrite": { ... },
  "maxS3Read": { ... },
  "maxS3Write": { ... }
}
```

## Project Standards

See [PROJECT_STANDARDS.md](PROJECT_STANDARDS.md) for detailed information on:
- Development environment setup
- Port configuration (using port 5060)
- Code quality standards
- Testing requirements
- Deployment guidelines
- Security practices
- Documentation requirements

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
