import React, { useState, useEffect } from 'react';

/**
 * ToastNotification Component
 * 
 * Gothic-themed notification system that replaces browser alert()
 * Auto-dismisses after specified time
 * Supports success, error, info, warning types
 * Stacks multiple toasts
 * 
 * Usage:
 *   const [toasts, setToasts] = useState([]);
 *   
 *   const addToast = (message, type = 'info') => {
 *     const id = Date.now();
 *     setToasts(prev => [...prev, { id, message, type }]);
 *   };
 *   
 *   <ToastContainer toasts={toasts} onRemove={(id) => 
 *     setToasts(prev => prev.filter(t => t.id !== id))
 *   } />
 */

const ToastContainer = ({ toasts, onRemove }) => {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: '20px',
      right: '20px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      maxWidth: '400px',
      width: '100%'
    }}>
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          {...toast}
          onRemove={() => onRemove(toast.id)}
        />
      ))}
    </div>
  );
};

const Toast = ({ id, message, type = 'info', onRemove, duration = 5000 }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    // Fade in
    const fadeInTimer = setTimeout(() => setIsVisible(true), 10);
    
    // Auto-dismiss
    const dismissTimer = setTimeout(() => {
      handleDismiss();
    }, duration);

    return () => {
      clearTimeout(fadeInTimer);
      clearTimeout(dismissTimer);
    };
  }, [duration]);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => {
      onRemove();
    }, 300); // Match animation duration
  };

  const getThemeColors = () => {
    switch (type) {
      case 'success':
        return {
          bg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          border: '#34d399',
          icon: '✅',
          shadow: 'rgba(16, 185, 129, 0.4)'
        };
      case 'error':
        return {
          bg: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
          border: '#f87171',
          icon: '❌',
          shadow: 'rgba(239, 68, 68, 0.4)'
        };
      case 'warning':
        return {
          bg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
          border: '#fbbf24',
          icon: '⚠️',
          shadow: 'rgba(245, 158, 11, 0.4)'
        };
      case 'info':
      default:
        return {
          bg: 'linear-gradient(135deg, #9d4edd 0%, #7b2cbf 100%)',
          border: '#c77dff',
          icon: 'ℹ️',
          shadow: 'rgba(157, 78, 221, 0.4)'
        };
    }
  };

  const theme = getThemeColors();

  return (
    <div
      style={{
        background: theme.bg,
        border: `2px solid ${theme.border}`,
        borderRadius: '10px',
        padding: '16px 20px',
        boxShadow: `0 4px 20px ${theme.shadow}`,
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        position: 'relative',
        transform: isExiting 
          ? 'translateX(120%)' 
          : isVisible 
            ? 'translateX(0)' 
            : 'translateX(120%)',
        opacity: isExiting ? 0 : isVisible ? 1 : 0,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        fontFamily: "'Crimson Text', serif",
        color: 'white',
        cursor: 'pointer',
        minWidth: '300px'
      }}
      onClick={handleDismiss}
    >
      {/* Icon */}
      <div style={{
        fontSize: '24px',
        flexShrink: 0
      }}>
        {theme.icon}
      </div>

      {/* Message */}
      <div style={{
        flex: 1,
        fontSize: '15px',
        lineHeight: '1.5',
        fontWeight: '500'
      }}>
        {message}
      </div>

      {/* Close Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleDismiss();
        }}
        style={{
          background: 'rgba(255, 255, 255, 0.2)',
          border: 'none',
          borderRadius: '50%',
          width: '24px',
          height: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          fontSize: '16px',
          color: 'white',
          flexShrink: 0,
          transition: 'background 0.2s'
        }}
        onMouseOver={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.3)'}
        onMouseOut={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.2)'}
        title="Dismiss"
      >
        ×
      </button>
    </div>
  );
};

// Hook for easy toast management
export const useToast = () => {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info', duration = 5000) => {
    const id = Date.now() + Math.random(); // Ensure unique ID
    setToasts(prev => [...prev, { id, message, type, duration }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const showSuccess = (message, duration) => addToast(message, 'success', duration);
  const showError = (message, duration) => addToast(message, 'error', duration);
  const showWarning = (message, duration) => addToast(message, 'warning', duration);
  const showInfo = (message, duration) => addToast(message, 'info', duration);

  return {
    toasts,
    addToast,
    removeToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    ToastContainer: () => <ToastContainer toasts={toasts} onRemove={removeToast} />
  };
};

export default ToastContainer;
export { Toast };

