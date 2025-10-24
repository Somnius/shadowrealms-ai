import React from 'react';

function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel, confirmText = "Confirm", cancelText = "Cancel" }) {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
        border: '3px solid #e94560',
        borderRadius: '15px',
        padding: '30px',
        maxWidth: '500px',
        width: '100%',
        boxShadow: '0 10px 40px rgba(233, 69, 96, 0.5), inset 0 0 20px rgba(0, 0, 0, 0.3)',
        animation: 'modalFadeIn 0.3s ease'
      }}>
        {/* Title */}
        <h2 style={{
          color: '#e94560',
          fontSize: '24px',
          marginBottom: '20px',
          fontFamily: 'Cinzel, serif',
          textAlign: 'center',
          textShadow: '0 0 10px rgba(233, 69, 96, 0.5)'
        }}>
          {title}
        </h2>

        {/* Message */}
        <div style={{
          color: '#d0d0e0',
          fontSize: '16px',
          lineHeight: '1.6',
          marginBottom: '30px',
          fontFamily: 'Crimson Text, serif',
          textAlign: 'center',
          whiteSpace: 'pre-line'
        }}>
          {message}
        </div>

        {/* Buttons */}
        <div style={{
          display: 'flex',
          gap: '15px',
          justifyContent: 'center'
        }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: '12px 24px',
              background: 'rgba(139, 139, 159, 0.2)',
              color: '#8b8b9f',
              border: '2px solid #8b8b9f',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: 'bold',
              fontFamily: 'Cinzel, serif',
              transition: 'all 0.2s',
              minHeight: '44px'
            }}
            onMouseOver={(e) => {
              e.target.style.background = 'rgba(139, 139, 159, 0.3)';
              e.target.style.borderColor = '#b5b5c3';
              e.target.style.color = '#b5b5c3';
            }}
            onMouseOut={(e) => {
              e.target.style.background = 'rgba(139, 139, 159, 0.2)';
              e.target.style.borderColor = '#8b8b9f';
              e.target.style.color = '#8b8b9f';
            }}
          >
            {cancelText}
          </button>

          <button
            onClick={onConfirm}
            autoFocus
            style={{
              flex: 1,
              padding: '12px 24px',
              background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              color: 'white',
              border: '2px solid #e94560',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: 'bold',
              fontFamily: 'Cinzel, serif',
              boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
              transition: 'all 0.2s',
              minHeight: '44px'
            }}
            onMouseOver={(e) => {
              e.target.style.boxShadow = '0 6px 25px rgba(233, 69, 96, 0.6)';
              e.target.style.transform = 'translateY(-2px)';
            }}
            onMouseOut={(e) => {
              e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
              e.target.style.transform = 'translateY(0)';
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes modalFadeIn {
          from {
            opacity: 0;
            transform: scale(0.9);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
}

export default ConfirmDialog;

