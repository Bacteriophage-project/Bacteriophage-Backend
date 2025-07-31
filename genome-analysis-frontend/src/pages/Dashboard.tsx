import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Grid,
  Chip,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  Divider,
  AlertTitle,
} from '@mui/material';
import {
  Download as DownloadIcon,
  BugReport as BugReportIcon,
  Science as ScienceIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import apiService, { GenomeData, JobStatus } from '../services/api';

const Dashboard = () => {
  const [bioprojectId, setBioprojectId] = useState('');
  const [genomeUrls, setGenomeUrls] = useState<GenomeData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [fetchJobId, setFetchJobId] = useState<string | null>(null);
  const [fetchStatus, setFetchStatus] = useState<JobStatus | null>(null);
  const [analysisJobs, setAnalysisJobs] = useState<{ [key: string]: JobStatus }>({});
  const [selectedGenome, setSelectedGenome] = useState<GenomeData | null>(null);
  const [infoModalOpen, setInfoModalOpen] = useState(false);
  const [showPhastestFallback, setShowPhastestFallback] = useState(false);
  const [downloadingFasta, setDownloadingFasta] = useState(false);
  const [phastestZipFiles, setPhastestZipFiles] = useState<Array<{ filename: string; size: number; size_mb: number }>>([]);
  const [loadingZipFiles, setLoadingZipFiles] = useState(false);
  const [tempFastaZipFiles, setTempFastaZipFiles] = useState<Array<{ 
    filename: string; 
    temp_dir: string; 
    full_path: string; 
    size: number; 
    size_mb: number; 
    created_time: number 
  }>>([]);
  const [loadingTempZipFiles, setLoadingTempZipFiles] = useState(false);

  // Poll for job status
  useEffect(() => {
    // Load PHASTEST zip files and temp FASTA zip files on component mount
    loadPhastestZipFiles();
    loadTempFastaZipFiles();
    
    const pollInterval = setInterval(async () => {
      if (fetchJobId) {
        try {
          const status = await apiService.getJobStatus(fetchJobId);
          setFetchStatus(status);
          
          if (status.status === 'completed' && status.result?.genomes) {
            setGenomeUrls(status.result.genomes);
            setFetchJobId(null);
          } else if (status.status === 'failed') {
            setError(status.error || 'Failed to fetch genomes');
            setFetchJobId(null);
          }
        } catch (err) {
          console.error('Error polling job status:', err);
        }
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [fetchJobId]);

  // Poll for analysis job status
  useEffect(() => {
    const pollInterval = setInterval(async () => {
      const jobsToPoll = Object.entries(analysisJobs).filter(([_, job]) => 
        job && ['pending', 'running'].includes(job.status)
      );

      for (const [type, job] of jobsToPoll) {
        if (job) {
          try {
            const status = await apiService.getJobStatus(job.job_id);
            setAnalysisJobs(prev => ({
              ...prev,
              [type]: status
            }));
            
            // If PHASTEST job completed, refresh zip files list
            if (type === 'phastest' && status.status === 'completed') {
              loadPhastestZipFiles();
            }
          } catch (err) {
            console.error(`Error polling ${type} job status:`, err);
          }
        }
      }
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [analysisJobs]);



  const handleManualDownload = async (type: string, jobId: string) => {
    try {
      const fileType = type === 'vfdb' ? 'vfdb_excel' : `${type}_csv`;
      const blob = await apiService.downloadFile(jobId, fileType);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = type === 'vfdb' ? 'vfdb_results.xlsx' : `${type}_results.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(`Failed to download ${type} results: ${err.message}`);
    }
  };

  const handleFetchGenomes = async () => {
    if (!bioprojectId.trim()) {
      setError('Please enter a BioProject ID');
      return;
    }

    setLoading(true);
    setError(null);
    setFetchStatus(null);

    try {
      const response = await apiService.fetchGenomes(bioprojectId);
      setFetchJobId(response.job_id);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start genome fetching');
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysis = async (type: 'resfinder' | 'phastest' | 'vfdb') => {
    try {
      setError(null);
      
      // Special handling for PHASTEST
      if (type === 'phastest') {
        try {
          // Check PHASTEST API status first
          const statusResponse = await apiService.checkPhastestStatus();
          if (statusResponse.status === 'unavailable') {
            setShowPhastestFallback(true);
            return;
          }
        } catch (statusError) {
          setShowPhastestFallback(true);
          return;
        }
      }
      
      let response;
      switch (type) {
        case 'resfinder':
          response = await apiService.runResFinder(genomeUrls);
          break;
        case 'phastest':
          response = await apiService.runPhastest(genomeUrls);
          break;
        case 'vfdb':
          response = await apiService.runVfdb(genomeUrls);
          break;
        default:
          throw new Error(`Unknown analysis type: ${type}`);
      }
      
      const jobId = response.job_id;
      
      setAnalysisJobs(prev => ({
        ...prev,
        [type]: {
          job_id: jobId,
          job_type: type,
          status: 'pending',
          progress: 0,
          result: null,
          error: null,
          created_at: new Date().toISOString(),
          completed_at: null
        }
      }));
      
      // Poll for job status
      const pollInterval = setInterval(async () => {
        try {
          const jobStatus = await apiService.getJobStatus(jobId);
          setAnalysisJobs(prev => ({
            ...prev,
            [type]: jobStatus
          }));
          
          if (jobStatus.status === 'completed' || jobStatus.status === 'failed') {
            clearInterval(pollInterval);
          }
        } catch (err) {
          console.error('Error polling job status:', err);
          clearInterval(pollInterval);
        }
      }, 2000);
      
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || `Failed to start ${type} analysis`);
    }
  };

  const handlePhastestFallback = async () => {
    try {
      setDownloadingFasta(true);
      setError(null);
      
      console.log('Downloading FASTA files from ResFinder results...');
      
      // Create a direct download link instead of handling blob
      const downloadUrl = `${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api/download-resfinder-fasta-zip`;
      console.log('Direct download URL:', downloadUrl);
      
      // Create a temporary link and trigger download
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'phastest_fasta_files.zip';
      link.target = '_blank'; // Open in new tab to avoid timeout issues
      
      console.log('Triggering direct download...');
      
      // Ensure the link is properly configured for download
      link.style.display = 'none';
      link.setAttribute('download', 'phastest_fasta_files.zip');
      
      document.body.appendChild(link);
      
      // Trigger the download
      link.click();
      
      // Clean up
      setTimeout(() => {
        document.body.removeChild(link);
      }, 100);
      
      setSuccessMessage('FASTA files download started! Check your downloads folder.');
      setShowPhastestFallback(false);
      
    } catch (err: any) {
      console.error('FASTA download error details:', {
        message: err.message,
        response: err.response,
        status: err.response?.status,
        statusText: err.response?.statusText,
        data: err.response?.data,
        stack: err.stack
      });
      setError('Failed to download FASTA files: ' + (err.response?.data?.error || err.message || 'Unknown error'));
    } finally {
      setDownloadingFasta(false);
    }
  };

  const loadPhastestZipFiles = async () => {
    try {
      setLoadingZipFiles(true);
      const response = await apiService.listPhastestZipFiles();
      setPhastestZipFiles(response.zip_files);
    } catch (err) {
      console.error('Failed to load PHASTEST zip files:', err);
    } finally {
      setLoadingZipFiles(false);
    }
  };

  const loadTempFastaZipFiles = async () => {
    try {
      setLoadingTempZipFiles(true);
      const response = await apiService.listTempFastaZipFiles();
      setTempFastaZipFiles(response.zip_files);
    } catch (err) {
      console.error('Failed to load temporary FASTA zip files:', err);
    } finally {
      setLoadingTempZipFiles(false);
    }
  };

  const handleDownloadTempFastaZip = async (tempDir: string, filename: string) => {
    try {
      const blob = await apiService.downloadTempFastaZip(tempDir, filename);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Failed to download temporary FASTA zip file: ' + err.message);
    }
  };

  const handleDownloadPhastestZip = async () => {
    try {
      // Find the most recent PHASTEST job
      const phastestJob = Object.values(analysisJobs).find(job => job?.job_type === 'phastest' && job?.status === 'completed');
      if (!phastestJob) {
        setError('No completed PHASTEST job found');
        return;
      }
      
      const blob = await apiService.downloadFile(phastestJob.job_id, 'phastest_zip');
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `phastest_results_${phastestJob.job_id}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Failed to download PHASTEST zip files: ' + err.message);
    }
  };

  const handleInfoClick = (genome: GenomeData) => {
    setSelectedGenome(genome);
    setInfoModalOpen(true);
  };

  const handleCloseInfoModal = () => {
    setInfoModalOpen(false);
    setSelectedGenome(null);
  };

  const getAnalysisIcon = (type: string) => {
    switch (type) {
      case 'resfinder': return <BugReportIcon />;
      case 'phastest': return <ScienceIcon />;
      case 'vfdb': return <ScienceIcon />;
      default: return <ScienceIcon />;
    }
  };

  const getAnalysisTitle = (type: string) => {
    switch (type) {
      case 'resfinder': return 'ResFinder (AMR)';
      case 'phastest': return 'PHASTEST (Prophages)';
      case 'vfdb': return 'VFDB (Virulence Factors)';
      default: return type;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'running': return 'warning';
      default: return 'default';
    }
  };

  // Move operation buttons to the top of the analysis section
  const renderOperationButtons = () => (
    <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
      {(['resfinder', 'phastest', 'vfdb'] as const).map((type) => {
        const job = analysisJobs[type];
        const isRunning = job && ['pending', 'running'].includes(job.status);
        return (
          <Button
            key={type}
            variant="contained"
            onClick={() => handleRunAnalysis(type)}
            disabled={loading || isRunning}
            startIcon={isRunning ? <CircularProgress size={20} /> : getAnalysisIcon(type)}
            sx={{ minWidth: 180 }}
          >
            {isRunning ? 'Running...' : `Run ${getAnalysisTitle(type)}`}
          </Button>
        );
      })}
    </Box>
  );

  // Compact genome table
  const renderGenomeTable = () => (
    <TableContainer component={Paper} sx={{ mb: 3 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Submitter</TableCell>
            <TableCell>Date</TableCell>
            <TableCell>URL</TableCell>
            <TableCell>Info</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {genomeUrls.map((genome, index) => (
            <TableRow key={index}>
              <TableCell>{index + 1}</TableCell>
              <TableCell>{genome.species || genome.assembly_name || genome.genus}</TableCell>
              <TableCell>{genome.submitter}</TableCell>
              <TableCell>{genome.submission_date}</TableCell>
              <TableCell>
                <Tooltip title={genome.url} placement="top" arrow>
                  <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block', whiteSpace: 'nowrap', verticalAlign: 'bottom' }}>{genome.url}</span>
                </Tooltip>
              </TableCell>
              <TableCell>
                <IconButton 
                  size="small" 
                  onClick={() => handleInfoClick(genome)}
                  title="View detailed information"
                >
                  <InfoIcon fontSize="small" />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const renderPhastestFallback = () => (
    <Alert severity="warning" sx={{ mb: 3 }}>
      <AlertTitle>PHASTEST API Unavailable</AlertTitle>
      The PHASTEST API is currently down for maintenance or updates.
      <Box sx={{ mt: 2 }}>
        <Button
          variant="outlined"
          onClick={handlePhastestFallback}
          disabled={downloadingFasta}
          startIcon={downloadingFasta ? <CircularProgress size={20} /> : <DownloadIcon />}
        >
          {downloadingFasta ? 'Downloading...' : 'Download FASTA Files from ResFinder Results'}
        </Button>
      </Box>
      <Typography variant="body2" sx={{ mt: 1 }}>
        After downloading, visit{' '}
        <a href="https://phastest.ca" target="_blank" rel="noopener noreferrer">
          phastest.ca
        </a>{' '}
        to submit your files manually.
      </Typography>
    </Alert>
  );

  const renderGenomeInfoModal = () => (
    <Dialog 
      open={infoModalOpen} 
      onClose={handleCloseInfoModal}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <InfoIcon color="primary" />
          <Typography variant="h6">
            Genome Details
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent>
        {selectedGenome && (
          <List>
            <ListItem>
              <ListItemText 
                primary="Organism Information"
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Organism:</strong> {selectedGenome.organism || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Genus:</strong> {selectedGenome.genus || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Species:</strong> {selectedGenome.species || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Strain:</strong> {selectedGenome.strain || 'N/A'}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText 
                primary="Assembly Information"
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Assembly Accession:</strong> {selectedGenome.assembly_accession || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Assembly Name:</strong> {selectedGenome.assembly_name || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Assembly Level:</strong> {selectedGenome.assembly_level || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Taxonomy ID:</strong> {selectedGenome.taxonomy_id || 'N/A'}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText 
                primary="Genome Statistics"
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Contig Count:</strong> {selectedGenome.contig_count || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Genome Size:</strong> {selectedGenome.genome_size || 'N/A'}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText 
                primary="Submission Information"
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Submitter:</strong> {selectedGenome.submitter || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Submission Date:</strong> {selectedGenome.submission_date || 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>BioProject ID:</strong> {selectedGenome.bioproject_id || 'N/A'}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText 
                primary="Download URL"
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography 
                      variant="body2" 
                      color="primary" 
                      sx={{ 
                        wordBreak: 'break-all',
                        fontFamily: 'monospace',
                        fontSize: '0.875rem'
                      }}
                    >
                      {selectedGenome.url}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCloseInfoModal} color="primary">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Bacteriophage
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Input Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Fetch Genomes
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="BioProject ID"
                value={bioprojectId}
                onChange={(e) => setBioprojectId(e.target.value)}
                placeholder="e.g., PRJNA123456"
                disabled={loading || !!fetchJobId}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Button
                variant="contained"
                onClick={handleFetchGenomes}
                disabled={loading || !!fetchJobId || !bioprojectId.trim()}
                startIcon={fetchJobId ? <CircularProgress size={20} /> : <DownloadIcon />}
                sx={{ minWidth: 200 }}
              >
                {fetchJobId ? 'Fetching...' : 'Fetch Genomes'}
              </Button>
            </Grid>
          </Grid>

          {fetchStatus && (
            <Box sx={{ mt: 2 }}>
              <Chip
                label={`Status: ${fetchStatus.status}`}
                color={getStatusColor(fetchStatus.status) as any}
                sx={{ mr: 1 }}
              />
              {fetchStatus.status === 'completed' && (
                <Chip
                  label={`${fetchStatus.result?.count || 0} genomes found`}
                  color="success"
                />
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* PHASTEST Fallback Alert */}
      {showPhastestFallback && genomeUrls.length > 0 && renderPhastestFallback()}
      
      {/* PHASTEST API Down but no genomes */}
      {showPhastestFallback && genomeUrls.length === 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <AlertTitle>PHASTEST API Unavailable</AlertTitle>
          The PHASTEST API is currently down for maintenance or updates.
          <Typography variant="body2" sx={{ mt: 1 }}>
            Please fetch genomes first, then you can download FASTA files for manual submission to{' '}
            <a href="https://phastest.ca" target="_blank" rel="noopener noreferrer">
              phastest.ca
            </a>
          </Typography>
        </Alert>
      )}

      {/* Operation Buttons at the Top */}
      {genomeUrls.length > 0 && renderOperationButtons()}

      {/* Analysis Status & Downloads */}
      {genomeUrls.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Analysis Status & Downloads
            </Typography>
            <Grid container spacing={3}>
              {(['resfinder', 'phastest', 'vfdb'] as const).map((type) => {
                const job = analysisJobs[type];
                const isCompleted = job && job.status === 'completed';
                const isFailed = job && job.status === 'failed';
                return (
                  <Grid item xs={12} md={4} key={type}>
                    <Card variant="outlined" sx={{ height: '100%' }}>
                      <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                          {getAnalysisIcon(type)}
                          <Typography variant="h6" sx={{ ml: 1 }}>
                            {getAnalysisTitle(type)}
                          </Typography>
                        </Box>
                        {job && (
                          <Box sx={{ mb: 2 }}>
                            <Chip
                              label={job.status}
                              color={getStatusColor(job.status) as any}
                              size="small"
                            />
                          </Box>
                        )}
                        {isFailed && job.error && (
                          <Alert severity="error" sx={{ mb: 2 }}>
                            {job.error}
                          </Alert>
                        )}
                        {isCompleted && (
                          <button
                            className="download-results-button"
                            style={{
                              width: '100%',
                              marginTop: '8px',
                              padding: '12px 20px',
                              backgroundColor: '#1976d2',
                              color: 'white',
                              border: 'none',
                              borderRadius: '8px',
                              fontSize: '14px',
                              fontWeight: '600',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '10px',
                              boxShadow: '0 2px 8px rgba(25, 118, 210, 0.3)',
                              outline: 'none',
                              textDecoration: 'none',
                              textTransform: 'none',
                              minHeight: '44px',
                              transition: 'all 0.2s ease-in-out',
                              position: 'relative',
                              overflow: 'hidden',
                            }}
                            onMouseOver={(e) => {
                              const target = e.target as HTMLButtonElement;
                              target.style.backgroundColor = '#1565c0';
                              target.style.boxShadow = '0 4px 12px rgba(25, 118, 210, 0.4)';
                              target.style.transform = 'translateY(-1px)';
                            }}
                            onMouseOut={(e) => {
                              const target = e.target as HTMLButtonElement;
                              target.style.backgroundColor = '#1976d2';
                              target.style.boxShadow = '0 2px 8px rgba(25, 118, 210, 0.3)';
                              target.style.transform = 'translateY(0)';
                            }}
                            onMouseDown={(e) => {
                              const target = e.target as HTMLButtonElement;
                              target.style.transform = 'translateY(0)';
                              target.style.boxShadow = '0 1px 4px rgba(25, 118, 210, 0.3)';
                            }}
                            onMouseUp={(e) => {
                              const target = e.target as HTMLButtonElement;
                              target.style.transform = 'translateY(-1px)';
                              target.style.boxShadow = '0 4px 12px rgba(25, 118, 210, 0.4)';
                            }}
                            onClick={() => handleManualDownload(type, job.job_id)}
                          >
                            <DownloadIcon style={{ 
                              fontSize: '18px', 
                              color: 'white',
                              transition: 'transform 0.2s ease-in-out'
                            }} />
                            Download Results
                          </button>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* PHASTEST Zip Files Section */}
      {phastestZipFiles.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                PHASTEST Zip Files ({phastestZipFiles.length})
              </Typography>
              <Button
                variant="contained"
                onClick={handleDownloadPhastestZip}
                startIcon={<DownloadIcon />}
                disabled={loadingZipFiles}
                sx={{
                  borderRadius: '8px',
                  textTransform: 'none',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                }}
              >
                Download All ZIP Files
              </Button>
            </Box>
            <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Filename</TableCell>
                    <TableCell align="right">Size (MB)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {phastestZipFiles.map((file, index) => (
                    <TableRow key={index}>
                      <TableCell>{file.filename}</TableCell>
                      <TableCell align="right">{file.size_mb}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Temporary FASTA Zip Files Section */}
      {tempFastaZipFiles.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Temporary FASTA Zip Files ({tempFastaZipFiles.length})
              </Typography>
              <Button
                variant="outlined"
                onClick={loadTempFastaZipFiles}
                startIcon={<DownloadIcon />}
                disabled={loadingTempZipFiles}
              >
                Refresh List
              </Button>
            </Box>
            <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Filename</TableCell>
                    <TableCell>Directory</TableCell>
                    <TableCell align="right">Size (MB)</TableCell>
                    <TableCell align="right">Created</TableCell>
                    <TableCell align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tempFastaZipFiles.map((file, index) => (
                    <TableRow key={index}>
                      <TableCell>{file.filename}</TableCell>
                      <TableCell>{file.temp_dir}</TableCell>
                      <TableCell align="right">{file.size_mb}</TableCell>
                      <TableCell align="right">
                        {new Date(file.created_time * 1000).toLocaleString()}
                      </TableCell>
                      <TableCell align="center">
                        <Button
                          variant="contained"
                          size="small"
                          onClick={() => handleDownloadTempFastaZip(file.temp_dir, file.filename)}
                          startIcon={<DownloadIcon />}
                          sx={{
                            borderRadius: '6px',
                            textTransform: 'none',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                          }}
                        >
                          Download
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Compact Genome Table */}
      {genomeUrls.length > 0 && renderGenomeTable()}

      {/* Genome Info Modal */}
      {renderGenomeInfoModal()}
    </Box>
  );
};

export default Dashboard; 