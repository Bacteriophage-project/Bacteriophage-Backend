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
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  TableChart as TableIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import apiService, { JobStatus } from '../services/api';

const Results = () => {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);


  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const response = await apiService.listJobs();
      setJobs(response.jobs.filter(job => job.status === 'completed'));
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

  const columns: GridColDef[] = [
    {
      field: 'job_type',
      headerName: 'Analysis Type',
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
        
        return (
          <Box sx={{ display: 'flex', gap: 1 }}>
            {isAnalysisJob && (
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
            {job.job_type === 'phastest' && (
              <IconButton
                size="small"
                onClick={() => handleDownload(job.job_id, 'phastest_zip')}
                title="Download PHASTEST ZIP Files"
                sx={{ color: 'warning.main' }}
              >
                <DownloadIcon />
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

  if (loading) {
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
          Analysis Results
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

      {jobs.length === 0 ? (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <TableIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No completed analyses found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Run analyses from the Dashboard to see results here
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Completed Analyses ({jobs.length})
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
      )}
    </Box>
  );
};

export default Results; 