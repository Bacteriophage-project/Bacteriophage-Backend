# Genome Analysis Tool - React Frontend

A professional, modern React frontend for the Genome Analysis Tool that provides a user-friendly interface for running ResFinder, PHASTEST, and VFDB analyses.

## Features

- **Modern UI**: Built with Material-UI for a professional, responsive design
- **Real-time Monitoring**: Live job status updates and progress tracking
- **File Management**: Download analysis results in CSV/Excel format
- **Job History**: View and manage all completed and running jobs
- **Error Handling**: Comprehensive error handling and user feedback

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- The Flask API server running on `http://localhost:5000`

## Installation

1. **Install dependencies:**
   ```bash
   cd genome-analysis-frontend
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm start
   ```

3. **Open your browser:**
   Navigate to `http://localhost:3000`

## Usage

### Dashboard
- Enter a BioProject ID to fetch genomes from NCBI
- Run ResFinder (AMR), PHASTEST (Prophages), or VFDB (Virulence Factors) analyses
- Monitor job progress in real-time
- Download results when analysis is complete

### Results
- View all completed analyses
- Download result files
- Filter and sort results

### Jobs
- Monitor all running and completed jobs
- Delete completed jobs to free up space
- View job statistics and status

## API Endpoints

The frontend communicates with the Flask API server on the following endpoints:

- `GET /api/health` - Health check
- `POST /api/fetch-genomes` - Fetch genomes from NCBI
- `POST /api/run-resfinder` - Run ResFinder analysis
- `POST /api/run-phastest` - Run PHASTEST analysis
- `POST /api/run-vfdb` - Run VFDB analysis
- `GET /api/job-status/{job_id}` - Get job status
- `GET /api/jobs` - List all jobs
- `GET /api/download/{job_id}/{file_type}` - Download result files
- `DELETE /api/cleanup/{job_id}` - Clean up job data

## Project Structure

```
src/
├── components/
│   └── Header.tsx          # Navigation header
├── pages/
│   ├── Dashboard.tsx       # Main analysis interface
│   ├── Results.tsx         # Results display
│   └── Jobs.tsx           # Job monitoring
├── services/
│   └── api.ts             # API service functions
├── App.tsx                # Main app component
└── index.tsx              # App entry point
```

## Technologies Used

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI** - Component library
- **React Router** - Navigation
- **Axios** - HTTP client
- **DataGrid** - Data tables

## Development

### Available Scripts

- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm eject` - Eject from Create React App

### Environment Variables

Create a `.env` file in the root directory:

```env
REACT_APP_API_URL=http://localhost:5000/api
```

## Production Build

1. **Build the application:**
   ```bash
   npm run build
   ```

2. **Serve the build folder:**
   ```bash
   npx serve -s build
   ```

## Troubleshooting

### Common Issues

1. **API Connection Error**
   - Ensure the Flask API server is running on port 5000
   - Check CORS settings in the API server

2. **Module Not Found Errors**
   - Run `npm install` to install missing dependencies
   - Clear node_modules and reinstall if needed

3. **TypeScript Errors**
   - Ensure all dependencies are properly installed
   - Check TypeScript configuration in `tsconfig.json`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of the Genome Analysis Tool suite. 