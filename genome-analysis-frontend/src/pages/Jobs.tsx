import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Paper,
  IconButton,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import apiService, { JobStatus } from '../services/api';

const Jobs = () => {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000); // Auto-refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadJobs = async () => {
    try {
      const response = await apiService.listJobs();
      setJobs(response.jobs);
    } catch (err: any) {
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      await apiService.cleanupJob(jobId);
      setJobs(jobs.filter(job => job.job_id !== jobId));
    } catch (err: any) {
      setError('Failed to delete job');
    }
  };

  const handleDownload = async (jobId: string, fileType: string) => {
    try {
      const blob = await apiService.downloadFile(jobId, fileType);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Set appropriate filename based on job type and file type
      let filename = 'results';
      if (fileType.includes('vfdb')) {
        filename = 'vfdb_results.xlsx';
      } else if (fileType.includes('resfinder')) {
        filename = 'resfinder_results.csv';
      } else if (fileType === 'phastest_csv') {
        filename = 'phastest_results.csv';
      } else if (fileType === 'phastest_zip') {
        filename = `phastest_results_${jobId}.zip`;
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Failed to download file');
    }
  };

  const handleStopJob = async (jobId: string) => {
    setActionLoading(jobId + '-stop');
    try {
      await apiService.stopJob(jobId);
      loadJobs();
    } catch (err: any) {
      setError('Failed to stop job');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResumeJob = async (jobId: string) => {
    setActionLoading(jobId + '-resume');
    try {
      await apiService.resumeJob(jobId);
      loadJobs();
    } catch (err: any) {
      setError('Failed to resume job');
    } finally {
      setActionLoading(null);
    }
  };

  const getJobTypeLabel = (type: string) => {
    switch (type) {
      case 'resfinder': return 'ResFinder (AMR)';
      case 'phastest': return 'PHASTEST (Prophages)';
      case 'vfdb': return 'VFDB (Virulence Factors)';
      case 'fetch_genomes': return 'Genome Fetch';
      default: return type;
    }
  };

  const getJobTypeColor = (type: string) => {
    switch (type) {
      case 'resfinder': return 'error';
      case 'phastest': return 'warning';
      case 'vfdb': return 'info';
      case 'fetch_genomes': return 'success';
      default: return 'default';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'running': return 'warning';
      case 'pending': return 'info';
      default: return 'default';
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'job_type',
      headerName: 'Job Type',
      width: 200,
      renderCell: (params) => (
        <Chip
          label={getJobTypeLabel(params.value)}
          color={getJobTypeColor(params.value) as any}
          size="small"
        />
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={getStatusColor(params.value) as any}
          size="small"
        />
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 180,
      valueFormatter: (params) => new Date(params.value).toLocaleString(),
    },
    {
      field: 'completed_at',
      headerName: 'Completed',
      width: 180,
      valueFormatter: (params) => params.value ? new Date(params.value).toLocaleString() : '-',
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 320,
      sortable: false,
      renderCell: (params) => {
        const job = params.row;
        const isAnalysisJob = ['resfinder', 'phastest', 'vfdb'].includes(job.job_type);
        const isCompleted = job.status === 'completed';
        const isRunning = job.status === 'running';
        const isPaused = job.status === 'paused';
        return (
          <Box sx={{ display: 'flex', gap: 1 }}>
            {isAnalysisJob && isCompleted && (
              <Button
                size="small"
                variant="contained"
                onClick={() => handleDownload(job.job_id, `${job.job_type}_csv`)}
                startIcon={<DownloadIcon />}
                sx={{
                  borderRadius: '8px',
                  textTransform: 'none',
                  fontSize: '0.75rem',
                  fontWeight: 500,
                  minWidth: 'auto',
                  padding: '6px 12px',
                }}
              >
                Download
              </Button>
            )}
            {job.job_type === 'phastest' && isCompleted && (
              <IconButton
                size="small"
                onClick={() => handleDownload(job.job_id, 'phastest_zip')}
                title="Download PHASTEST ZIP Files"
                sx={{ color: 'warning.main' }}
              >
                <DownloadIcon />
              </IconButton>
            )}
            {isAnalysisJob && isRunning && (
              <IconButton
                size="small"
                onClick={() => handleStopJob(job.job_id)}
                title="Stop Job"
                disabled={actionLoading === job.job_id + '-stop'}
                color="warning"
              >
                {actionLoading === job.job_id + '-stop' ? <CircularProgress size={18} /> : <StopIcon />}
              </IconButton>
            )}
            {isAnalysisJob && isPaused && (
              <IconButton
                size="small"
                onClick={() => handleResumeJob(job.job_id)}
                title="Resume Job"
                disabled={actionLoading === job.job_id + '-resume'}
                color="primary"
              >
                {actionLoading === job.job_id + '-resume' ? <CircularProgress size={18} /> : <PlayArrowIcon />}
              </IconButton>
            )}
            <IconButton
              size="small"
              onClick={() => handleDeleteJob(job.job_id)}
              title="Delete Job"
              color="error"
            >
              <DeleteIcon />
            </IconButton>
          </Box>
        );
      },
    },
  ];

  const runningJobs = jobs.filter(job => ['pending', 'running'].includes(job.status));
  const completedJobs = jobs.filter(job => job.status === 'completed');
  const failedJobs = jobs.filter(job => job.status === 'failed');

  if (loading && jobs.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">
          Job Monitor
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={loadJobs}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Summary Cards */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Card sx={{ flex: 1 }}>
          <CardContent sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="warning.main">
              {runningJobs.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Running Jobs
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1 }}>
          <CardContent sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="success.main">
              {completedJobs.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Completed Jobs
            </Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1 }}>
          <CardContent sx={{ textAlign: 'center' }}>
            <Typography variant="h4" color="error.main">
              {failedJobs.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Failed Jobs
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Jobs Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            All Jobs ({jobs.length})
          </Typography>
          <Paper sx={{ height: 600, width: '100%' }}>
            <DataGrid
              rows={jobs}
              columns={columns}
              getRowId={(row) => row.job_id}
              initialState={{
                pagination: {
                  paginationModel: { pageSize: 10 },
                },
              }}
              pageSizeOptions={[10, 25, 50]}
              disableRowSelectionOnClick
              sx={{
                '& .MuiDataGrid-cell:focus': {
                  outline: 'none',
                },
              }}
            />
          </Paper>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Jobs; 