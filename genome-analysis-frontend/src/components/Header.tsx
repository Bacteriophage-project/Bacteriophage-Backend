import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Science as ScienceIcon,
  Assessment as AssessmentIcon,
  Work as WorkIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const Header: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const navItems = [
    { label: 'Dashboard', path: '/', icon: <ScienceIcon /> },
    { label: 'Results', path: '/results', icon: <AssessmentIcon /> },
    { label: 'Jobs', path: '/jobs', icon: <WorkIcon /> },
  ];

  return (
    <AppBar position="static" elevation={0} sx={{ backgroundColor: 'white', borderBottom: '1px solid #e0e0e0' }}>
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <ScienceIcon sx={{ color: 'primary.main', mr: 2, fontSize: 32 }} />
          <Typography
            variant="h5"
            component="div"
            sx={{
              color: 'primary.main',
              fontWeight: 700,
              cursor: 'pointer',
            }}
            onClick={() => navigate('/')}
          >
            Genome Analysis Tool
          </Typography>
        </Box>

        {!isMobile && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            {navItems.map((item) => (
              <Button
                key={item.path}
                startIcon={item.icon}
                onClick={() => navigate(item.path)}
                sx={{
                  color: location.pathname === item.path ? 'primary.main' : 'text.secondary',
                  backgroundColor: location.pathname === item.path ? 'primary.50' : 'transparent',
                  '&:hover': {
                    backgroundColor: location.pathname === item.path ? 'primary.100' : 'grey.100',
                  },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>
        )}

        {isMobile && (
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {navItems.map((item) => (
              <IconButton
                key={item.path}
                onClick={() => navigate(item.path)}
                sx={{
                  color: location.pathname === item.path ? 'primary.main' : 'text.secondary',
                  backgroundColor: location.pathname === item.path ? 'primary.50' : 'transparent',
                }}
              >
                {item.icon}
              </IconButton>
            ))}
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header; 