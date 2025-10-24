import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';

function AdminPage({ token, user, onBack }) {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showBanModal, setShowBanModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [moderationLog, setModerationLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch all users on mount
  useEffect(() => {
    fetchUsers();
    fetchModerationLog();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await api.getAllUsers(token);
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (err) {
      setError('Failed to load users');
    }
  };

  const fetchModerationLog = async () => {
    try {
      const response = await api.getModerationLog(token, 20);
      if (response.ok) {
        const data = await response.json();
        setModerationLog(data);
      }
    } catch (err) {
      console.error('Failed to load moderation log');
    }
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    
    try {
      const response = await api.updateUser(token, selectedUser.id, {
        username: formData.get('username'),
        email: formData.get('email')
      });
      
      if (response.ok) {
        alert('✅ User updated!');
        setShowEditModal(false);
        fetchUsers();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update user');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    const newPassword = formData.get('new_password');
    
    try {
      const response = await api.resetUserPassword(token, selectedUser.id, newPassword);
      
      if (response.ok) {
        alert('✅ Password reset!');
        setShowPasswordModal(false);
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to reset password');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleBanUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    
    const banType = formData.get('ban_type');
    const banData = {
      ban_type: banType,
      ban_reason: formData.get('ban_reason')
    };
    
    if (banType === 'temporary') {
      banData.duration_hours = parseInt(formData.get('duration_hours') || 0);
      banData.duration_days = parseInt(formData.get('duration_days') || 0);
    }
    
    try {
      const response = await api.banUser(token, selectedUser.id, banData);
      
      if (response.ok) {
        alert('✅ User banned!');
        setShowBanModal(false);
        fetchUsers();
        fetchModerationLog();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to ban user');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleUnbanUser = async (userId) => {
    if (!window.confirm('Unban this user?')) return;
    
    try {
      const response = await api.unbanUser(token, userId);
      
      if (response.ok) {
        alert('✅ User unbanned!');
        fetchUsers();
        fetchModerationLog();
      }
    } catch (err) {
      setError('Failed to unban user');
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0f0f1e' }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
        padding: '20px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #2a2a4e'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <h1 style={{ color: '#e94560', margin: 0 }}>👑 Admin Panel</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span style={{ color: '#b5b5c3', fontWeight: '500' }}>👤 {user?.username}</span>
          <button
            onClick={onBack}
            style={{
              padding: '8px 16px',
              background: 'rgba(233, 69, 96, 0.2)',
              color: '#e94560',
              border: '2px solid #e94560',
              borderRadius: '5px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 20px' }}>
        
        {/* User Management Section */}
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '20px' }}>👥 User Management</h2>
          
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e',
            overflowX: 'auto'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #2a2a4e' }}>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>ID</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Username</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Email</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Role</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Status</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderBottom: '1px solid #2a2a4e' }}>
                    <td style={{ padding: '12px', color: '#b5b5c3' }}>{u.id}</td>
                    <td style={{ padding: '12px', color: '#fff', fontWeight: '600' }}>{u.username}</td>
                    <td style={{ padding: '12px', color: '#b5b5c3' }}>{u.email}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 12px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: '600',
                        background: u.role === 'admin' ? 'rgba(233, 69, 96, 0.2)' : 'rgba(40, 167, 69, 0.2)',
                        color: u.role === 'admin' ? '#e94560' : '#28a745',
                        border: `1px solid ${u.role === 'admin' ? '#e94560' : '#28a745'}`
                      }}>
                        {u.role === 'admin' ? '👑 Admin' : '🎮 Player'}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {u.is_banned ? (
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '600',
                          background: 'rgba(255, 68, 68, 0.2)',
                          color: '#ff4444',
                          border: '1px solid #ff4444'
                        }}>
                          🚫 {u.ban_type === 'permanent' ? 'PERMA BAN' : 'TEMP BAN'}
                        </span>
                      ) : (
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '600',
                          background: 'rgba(40, 167, 69, 0.2)',
                          color: '#28a745',
                          border: '1px solid #28a745'
                        }}>
                          ✅ Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          onClick={() => { setSelectedUser(u); setShowEditModal(true); }}
                          style={{
                            padding: '6px 12px',
                            background: '#667eea',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600'
                          }}
                        >
                          ✏️ Edit
                        </button>
                        <button
                          onClick={() => { setSelectedUser(u); setShowPasswordModal(true); }}
                          style={{
                            padding: '6px 12px',
                            background: '#ffa726',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600'
                          }}
                        >
                          🔑 Reset PW
                        </button>
                        {u.is_banned ? (
                          <button
                            onClick={() => handleUnbanUser(u.id)}
                            style={{
                              padding: '6px 12px',
                              background: '#28a745',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '12px',
                              fontWeight: '600'
                            }}
                          >
                            ✅ Unban
                          </button>
                        ) : (
                          <button
                            onClick={() => { setSelectedUser(u); setShowBanModal(true); }}
                            style={{
                              padding: '6px 12px',
                              background: '#dc3545',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '12px',
                              fontWeight: '600'
                            }}
                          >
                            🚫 Ban
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Moderation Log */}
        <div>
          <h2 style={{ color: '#e94560', marginBottom: '20px' }}>📋 Recent Moderation Log</h2>
          
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e'
          }}>
            {moderationLog.length === 0 ? (
              <p style={{ color: '#b5b5c3', textAlign: 'center' }}>No moderation actions yet</p>
            ) : (
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {moderationLog.map(log => (
                  <div key={log.id} style={{
                    padding: '12px',
                    marginBottom: '10px',
                    background: '#0f1729',
                    borderRadius: '8px',
                    border: '1px solid #2a2a4e'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: '#e94560', fontWeight: '600' }}>
                        {log.action.toUpperCase()}
                      </span>
                      <span style={{ color: '#8b8b9f', fontSize: '12px' }}>
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div style={{ color: '#b5b5c3', fontSize: '14px' }}>
                      <strong>{log.admin_username}</strong> → <strong>{log.username}</strong>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div style={{ color: '#8b8b9f', fontSize: '12px', marginTop: '4px' }}>
                        {JSON.stringify(log.details)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>✏️ Edit User</h3>
            <form onSubmit={handleEditUser}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Username:</label>
                <input
                  type="text"
                  name="username"
                  defaultValue={selectedUser.username}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Email:</label>
                <input
                  type="email"
                  name="email"
                  defaultValue={selectedUser.email}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#28a745',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showPasswordModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>🔑 Reset Password for {selectedUser.username}</h3>
            <form onSubmit={handleResetPassword}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>New Password:</label>
                <input
                  type="password"
                  name="new_password"
                  required
                  minLength={8}
                  placeholder="Minimum 8 characters"
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#ffa726',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Ban User Modal */}
      {showBanModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>🚫 Ban {selectedUser.username}</h3>
            <form onSubmit={handleBanUser}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Ban Type:</label>
                <select
                  name="ban_type"
                  required
                  onChange={(e) => {
                    document.getElementById('duration-fields').style.display = 
                      e.target.value === 'temporary' ? 'block' : 'none';
                  }}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                >
                  <option value="temporary">⏰ Temporary</option>
                  <option value="permanent">🔒 Permanent</option>
                </select>
              </div>
              
              <div id="duration-fields" style={{ marginBottom: '15px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Days:</label>
                    <input
                      type="number"
                      name="duration_days"
                      min="0"
                      defaultValue="0"
                      style={{
                        width: '100%',
                        padding: '10px',
                        background: '#0f1729',
                        border: '2px solid #2a2a4e',
                        borderRadius: '5px',
                        color: '#fff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Hours:</label>
                    <input
                      type="number"
                      name="duration_hours"
                      min="0"
                      defaultValue="0"
                      style={{
                        width: '100%',
                        padding: '10px',
                        background: '#0f1729',
                        border: '2px solid #2a2a4e',
                        borderRadius: '5px',
                        color: '#fff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>
              </div>
              
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Reason:</label>
                <textarea
                  name="ban_reason"
                  required
                  rows="3"
                  placeholder="Explain why this user is being banned..."
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    fontFamily: 'inherit',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Banning...' : '🚫 Ban User'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowBanModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#667eea',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          padding: '15px 25px',
          background: 'rgba(233, 69, 96, 0.9)',
          border: '2px solid #e94560',
          borderRadius: '8px',
          color: 'white',
          fontWeight: '500',
          zIndex: 2000
        }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}

export default AdminPage;

