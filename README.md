# Genome Analysis Tool

A comprehensive genome analysis platform that combines ResFinder (AMR), PHASTEST (Prophages), and VFDB (Virulence Factors) analyses with a modern React frontend and Flask API backend.

## 🚀 Quick Start

### Option 1: Automated Startup (Recommended)
```bash
python start_app.py
```
This will automatically:
- Check dependencies
- Install frontend packages
- Start both backend and frontend servers
- Open your browser

### Option 2: Manual Setup

#### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

#### 2. Start Flask API Server
```bash
python api_server.py
```
The API will be available at `http://localhost:5000`

#### 3. Install Frontend Dependencies
```bash
cd genome-analysis-frontend
npm install
```

#### 4. Start React Frontend
```bash
npm start
```
The frontend will be available at `http://localhost:3000`

## 🧬 Features

### Analysis Tools
- **ResFinder**: Antimicrobial Resistance (AMR) gene detection
- **PHASTEST**: Prophage prediction and analysis
- **VFDB**: Virulence Factor Database analysis

### User Interface
- **Modern React Frontend**: Professional Material-UI design
- **Real-time Monitoring**: Live job status and progress tracking
- **File Management**: Download results in CSV/Excel format
- **Job History**: View and manage all analyses
- **Responsive Design**: Works on desktop and mobile devices

### Backend API
- **RESTful API**: Clean, documented endpoints
- **Background Processing**: Non-blocking job execution
- **File Management**: Automatic result file handling
- **Error Handling**: Comprehensive error reporting

## 📁 Project Structure

```
Test_project/
├── api_server.py                    # Flask API server
├── requirements.txt                 # Python dependencies
├── start_app.py                     # Automated startup script
├── app.py                          # Original Streamlit app
├── utils/                          # Analysis utilities
│   ├── run_resfinder.py           # ResFinder analysis
│   ├── run_phastest.py            # PHASTEST analysis
│   ├── run_vfdb.py                # VFDB analysis
│   ├── ncbi_fetcher.py            # NCBI genome fetching
│   └── download_genomes.py        # Genome download utilities
├── genome-analysis-frontend/        # React frontend
│   ├── src/
│   │   ├── components/            # React components
│   │   ├── pages/                 # Page components
│   │   ├── services/              # API services
│   │   └── App.tsx               # Main app
│   ├── package.json              # Frontend dependencies
│   └── README.md                 # Frontend documentation
├── resfinder_results/              # ResFinder output
├── phastest_results/               # PHASTEST output
└── vfdb_results/                   # VFDB output
```

## 🔧 API Endpoints

### Core Endpoints
- `GET /api/health` - Health check
- `POST /api/fetch-genomes` - Fetch genomes from NCBI
- `POST /api/run-resfinder` - Run ResFinder analysis
- `POST /api/run-phastest` - Run PHASTEST analysis
- `POST /api/run-vfdb` - Run VFDB analysis

### Job Management
- `GET /api/job-status/{job_id}` - Get job status
- `GET /api/jobs` - List all jobs
- `GET /api/download/{job_id}/{file_type}` - Download results
- `DELETE /api/cleanup/{job_id}` - Clean up job data

## 💻 Usage

### 1. Fetch Genomes
1. Enter a BioProject ID (e.g., `PRJNA123456`)
2. Click "Fetch Genomes"
3. Wait for the genomes to be retrieved from NCBI

### 2. Run Analysis
1. Select the analysis type (ResFinder, PHASTEST, or VFDB)
2. Click "Run Analysis"
3. Monitor progress in real-time
4. Download results when complete

### 3. View Results
- **Dashboard**: Run new analyses and monitor active jobs
- **Results**: View and download completed analyses
- **Jobs**: Monitor all jobs and manage job history

## 🛠️ Development

### Backend Development
```bash
# Install development dependencies
pip install -r requirements.txt

# Run API server in development mode
python api_server.py
```

### Frontend Development
```bash
cd genome-analysis-frontend

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
```

### Environment Variables
Create a `.env` file in the frontend directory:
```env
REACT_APP_API_URL=http://localhost:5000/api
```

## 📊 Analysis Tools

### ResFinder (AMR)
- Detects antimicrobial resistance genes
- Uses BLAST against ResFinder database
- Outputs CSV with gene presence/absence matrix

### PHASTEST (Prophages)
- Predicts prophage regions in bacterial genomes
- Categorizes prophages as intact/incomplete/questionable
- Provides detailed prophage annotations

### VFDB (Virulence Factors)
- Identifies virulence factor genes
- Uses BLAST against VFDB database
- Outputs Excel file with gene categories

## 🔍 Troubleshooting

### Common Issues

1. **API Connection Error**
   - Ensure Flask server is running on port 5000
   - Check CORS settings
   - Verify network connectivity

2. **Analysis Failures**
   - Check if required databases are installed
   - Verify BLAST+ installation
   - Check disk space for results

3. **Frontend Issues**
   - Clear browser cache
   - Check Node.js version (v14+)
   - Reinstall dependencies if needed

### Dependencies
- **Python**: 3.7+
- **Node.js**: 14+
- **BLAST+**: For sequence analysis
- **ResFinder Database**: For AMR analysis
- **VFDB Database**: For virulence factor analysis

## 📝 License

This project is part of the Genome Analysis Tool suite.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the API documentation
3. Check existing issues in the repository 