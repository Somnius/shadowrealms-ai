import React from 'react';
import { 
  GothicBox, 
  SkullDivider, 
  OrnateDivider, 
  GothicButton,
  FloatingParticles,
  MagicCircle,
  BloodSplatter
} from '../components/GothicDecorations';

const GothicShowcase = ({ onBack }) => {
  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#0f0f1e', 
      color: '#b5b5c3',
      padding: '40px 20px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Floating Particles across entire page */}
      <FloatingParticles count={20} />

      {/* Random Blood Splatters */}
      <BloodSplatter style={{ top: '10%', left: '5%', width: '50px', height: '50px' }} />
      <BloodSplatter style={{ top: '30%', right: '10%', width: '40px', height: '40px' }} />
      <BloodSplatter style={{ bottom: '20%', left: '15%', width: '60px', height: '60px' }} />
      
      {/* Magic Circles */}
      <MagicCircle style={{ top: '15%', right: '5%' }} />
      <MagicCircle style={{ bottom: '30%', left: '8%' }} />

      <div style={{ maxWidth: '1200px', margin: '0 auto', position: 'relative', zIndex: 1 }}>
        
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '50px' }}>
          <h1 style={{ 
            fontSize: '48px', 
            color: '#e94560', 
            marginBottom: '20px',
            textShadow: '0 0 20px rgba(233, 69, 96, 0.5)',
            fontFamily: 'Cinzel, serif'
          }}>
            <i className="fas fa-skull"></i> SHADOWREALMS AI <i className="fas fa-skull"></i>
          </h1>
          <p style={{ 
            fontSize: '24px', 
            color: '#8b8b9f',
            fontFamily: 'Crimson Text, serif',
            fontStyle: 'italic'
          }}>
            Enter the realm of shadows and blood...
          </p>
          
          <button
            onClick={onBack}
            style={{
              marginTop: '20px',
              padding: '12px 30px',
              background: '#16213e',
              border: '2px solid #e94560',
              color: '#e94560',
              borderRadius: '5px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '16px',
              fontFamily: 'Cinzel, serif'
            }}
          >
            ← Back to Login
          </button>
        </div>

        <SkullDivider />

        {/* Gothic Box Example 1 - Login Style with Vampire Theme */}
        <GothicBox theme="vampire" style={{
          background: '#16213e',
          padding: '40px',
          borderRadius: '10px',
          marginBottom: '40px'
        }}>
          <h2 style={{ 
            color: '#e94560', 
            marginBottom: '25px',
            fontSize: '32px',
            fontFamily: 'Cinzel, serif',
            textAlign: 'center'
          }}>
            <i className="fas fa-book-dead"></i> Sign Your Pact
          </h2>
          
          <form style={{ maxWidth: '400px', margin: '0 auto' }}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                color: '#b5b5c3',
                fontFamily: 'Crimson Text, serif',
                fontSize: '18px'
              }}>
                <i className="fas fa-user-secret"></i> Username
              </label>
              <input
                type="text"
                placeholder="Enter the shadows..."
                style={{
                  width: '100%',
                  padding: '12px',
                  background: '#0f1729',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  color: '#e0e0e0',
                  fontSize: '16px',
                  fontFamily: 'Crimson Text, serif'
                }}
              />
            </div>
            
            <div style={{ marginBottom: '25px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                color: '#b5b5c3',
                fontFamily: 'Crimson Text, serif',
                fontSize: '18px'
              }}>
                <i className="fas fa-key"></i> Blood Seal
              </label>
              <input
                type="password"
                placeholder="Your secret covenant..."
                style={{
                  width: '100%',
                  padding: '12px',
                  background: '#0f1729',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  color: '#e0e0e0',
                  fontSize: '16px',
                  fontFamily: 'Crimson Text, serif'
                }}
              />
            </div>

            <GothicButton
              style={{
                width: '100%',
                padding: '15px',
                background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                border: 'none',
                borderRadius: '5px',
                color: 'white',
                fontSize: '18px',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif',
                boxShadow: '0 5px 20px rgba(233, 69, 96, 0.4)'
              }}
            >
              <i className="fas fa-sign-in-alt"></i> ENTER THE DARKNESS
            </GothicButton>
          </form>
        </GothicBox>

        <OrnateDivider icon="dragon" />

        {/* Gothic Box Example 2 - Campaign Card */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '30px',
          marginBottom: '40px'
        }}>
          <GothicBox theme="vampire" style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px'
          }}>
            <h3 style={{ 
              color: '#e94560', 
              marginBottom: '15px',
              fontSize: '24px',
              fontFamily: 'Cinzel, serif'
            }}>
              <i className="fas fa-book-skull"></i> Vampire: The Masquerade
            </h3>
            <p style={{ 
              color: '#b5b5c3', 
              lineHeight: '1.8',
              fontFamily: 'Crimson Text, serif',
              fontSize: '16px',
              marginBottom: '20px'
            }}>
              The night is eternal. Blood runs cold. The Camarilla watches from the shadows as ancient elders plot their dark games...
            </p>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '15px' }}>
              <span style={{ 
                padding: '5px 12px', 
                background: 'rgba(233, 69, 96, 0.2)', 
                border: '1px solid #e94560',
                borderRadius: '15px',
                fontSize: '12px',
                color: '#e94560'
              }}>
                <i className="fas fa-dice-d20"></i> World of Darkness
              </span>
              <span style={{ 
                padding: '5px 12px', 
                background: 'rgba(157, 78, 221, 0.2)', 
                border: '1px solid #9d4edd',
                borderRadius: '15px',
                fontSize: '12px',
                color: '#9d4edd'
              }}>
                <i className="fas fa-users"></i> 3 Players
              </span>
            </div>
            <GothicButton
              style={{
                width: '100%',
                padding: '12px',
                background: '#e94560',
                border: 'none',
                borderRadius: '5px',
                color: 'white',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif'
              }}
            >
              <i className="fas fa-door-open"></i> Enter Campaign
            </GothicButton>
          </GothicBox>

          <GothicBox theme="mage" style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px'
          }}>
            <h3 style={{ 
              color: '#9d4edd', 
              marginBottom: '15px',
              fontSize: '24px',
              fontFamily: 'Cinzel, serif'
            }}>
              <i className="fas fa-hat-wizard"></i> Mage: The Ascension
            </h3>
            <p style={{ 
              color: '#b5b5c3', 
              lineHeight: '1.8',
              fontFamily: 'Crimson Text, serif',
              fontSize: '16px',
              marginBottom: '20px'
            }}>
              Reality bends to your will. The Traditions gather as the Technocracy tightens its grip. Magic or science?
            </p>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '15px' }}>
              <span style={{ 
                padding: '5px 12px', 
                background: 'rgba(157, 78, 221, 0.2)', 
                border: '1px solid #9d4edd',
                borderRadius: '15px',
                fontSize: '12px',
                color: '#9d4edd'
              }}>
                <i className="fas fa-magic"></i> Sphere Magic
              </span>
              <span style={{ 
                padding: '5px 12px', 
                background: 'rgba(233, 69, 96, 0.2)', 
                border: '1px solid #e94560',
                borderRadius: '15px',
                fontSize: '12px',
                color: '#e94560'
              }}>
                <i className="fas fa-eye"></i> Reality War
              </span>
            </div>
            <GothicButton
              style={{
                width: '100%',
                padding: '12px',
                background: '#9d4edd',
                border: 'none',
                borderRadius: '5px',
                color: 'white',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif'
              }}
            >
              <i className="fas fa-wand-magic-sparkles"></i> Weave Reality
            </GothicButton>
          </GothicBox>
        </div>

        <SkullDivider />

        {/* Gothic Box Example 3 - Chat Interface */}
        <GothicBox style={{
          background: '#16213e',
          padding: '30px',
          borderRadius: '10px',
          marginBottom: '40px'
        }}>
          <h2 style={{ 
            color: '#e94560', 
            marginBottom: '25px',
            fontSize: '28px',
            fontFamily: 'Cinzel, serif',
            textAlign: 'center'
          }}>
            <i className="fas fa-comments"></i> The Dark Conclave
          </h2>
          
          <div style={{ 
            background: '#0f1729',
            border: '2px solid #2a2a4e',
            borderRadius: '8px',
            padding: '20px',
            marginBottom: '20px',
            maxHeight: '300px',
            overflowY: 'auto'
          }}>
            {/* Sample Messages */}
            {[
              { user: 'Marcus the Elder', msg: 'The Primogen Council convenes tonight. Be prepared.', type: 'npc' },
              { user: 'Isabella', msg: 'I sense a disturbance in the blood bond...', type: 'player' },
              { user: 'Storyteller', msg: '*The clock strikes midnight. Shadows grow longer.*', type: 'ai' },
              { user: 'Viktor', msg: 'My ghouls report movement in the sewers.', type: 'player' }
            ].map((m, i) => (
              <div key={i} style={{ 
                marginBottom: '15px',
                padding: '12px',
                background: m.type === 'ai' ? 'rgba(157, 78, 221, 0.1)' : 
                           m.type === 'npc' ? 'rgba(233, 69, 96, 0.1)' : 
                           'rgba(139, 139, 159, 0.05)',
                borderLeft: `3px solid ${m.type === 'ai' ? '#9d4edd' : m.type === 'npc' ? '#e94560' : '#8b8b9f'}`,
                borderRadius: '4px'
              }}>
                <div style={{ 
                  fontWeight: 'bold', 
                  color: m.type === 'ai' ? '#9d4edd' : m.type === 'npc' ? '#e94560' : '#b5b5c3',
                  marginBottom: '5px',
                  fontFamily: 'Cinzel, serif',
                  fontSize: '14px'
                }}>
                  {m.type === 'ai' && <i className="fas fa-robot"></i>}
                  {m.type === 'npc' && <i className="fas fa-crown"></i>}
                  {m.type === 'player' && <i className="fas fa-user"></i>}
                  {' '}{m.user}
                </div>
                <div style={{ 
                  color: '#d0d0d0',
                  fontFamily: 'Crimson Text, serif',
                  fontSize: '16px',
                  fontStyle: m.type === 'ai' ? 'italic' : 'normal'
                }}>
                  {m.msg}
                </div>
              </div>
            ))}
          </div>

          <form style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              placeholder="Whisper to the darkness..."
              style={{
                flex: 1,
                padding: '12px',
                background: '#0f1729',
                border: '2px solid #2a2a4e',
                borderRadius: '5px',
                color: '#e0e0e0',
                fontSize: '16px',
                fontFamily: 'Crimson Text, serif'
              }}
            />
            <GothicButton
              style={{
                padding: '12px 25px',
                background: '#e94560',
                border: 'none',
                borderRadius: '5px',
                color: 'white',
                fontWeight: 'bold',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif'
              }}
            >
              <i className="fas fa-paper-plane"></i> Send
            </GothicButton>
          </form>
        </GothicBox>

        <OrnateDivider icon="skull-crossbones" />

        {/* Gothic Box Example 4 - Admin Panel */}
        <GothicBox style={{
          background: '#16213e',
          padding: '30px',
          borderRadius: '10px',
          marginBottom: '40px'
        }}>
          <h2 style={{ 
            color: '#e94560', 
            marginBottom: '25px',
            fontSize: '28px',
            fontFamily: 'Cinzel, serif',
            textAlign: 'center'
          }}>
            <i className="fas fa-crown"></i> The Throne of Shadows
          </h2>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ 
              width: '100%', 
              borderCollapse: 'collapse',
              fontFamily: 'Crimson Text, serif'
            }}>
              <thead>
                <tr style={{ background: '#0f1729' }}>
                  <th style={{ padding: '12px', border: '1px solid #2a2a4e', textAlign: 'left', color: '#e94560', fontFamily: 'Cinzel, serif' }}>
                    <i className="fas fa-user"></i> Kindred
                  </th>
                  <th style={{ padding: '12px', border: '1px solid #2a2a4e', textAlign: 'left', color: '#e94560', fontFamily: 'Cinzel, serif' }}>
                    <i className="fas fa-flask"></i> Clan
                  </th>
                  <th style={{ padding: '12px', border: '1px solid #2a2a4e', textAlign: 'left', color: '#e94560', fontFamily: 'Cinzel, serif' }}>
                    <i className="fas fa-heart"></i> Status
                  </th>
                  <th style={{ padding: '12px', border: '1px solid #2a2a4e', textAlign: 'left', color: '#e94560', fontFamily: 'Cinzel, serif' }}>
                    <i className="fas fa-gavel"></i> Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: 'Marcus Blackwood', clan: 'Ventrue', status: 'Active' },
                  { name: 'Isabella Darkrose', clan: 'Toreador', status: 'Active' },
                  { name: 'Viktor Shadowfang', clan: 'Nosferatu', status: 'Banned' }
                ].map((char, i) => (
                  <tr key={i} style={{ background: char.status === 'Banned' ? 'rgba(233, 69, 96, 0.05)' : '#1a1a2e' }}>
                    <td style={{ padding: '12px', border: '1px solid #2a2a4e', color: '#d0d0d0' }}>{char.name}</td>
                    <td style={{ padding: '12px', border: '1px solid #2a2a4e', color: '#d0d0d0' }}>{char.clan}</td>
                    <td style={{ 
                      padding: '12px', 
                      border: '1px solid #2a2a4e', 
                      color: char.status === 'Banned' ? '#e94560' : '#28a745',
                      fontWeight: 'bold'
                    }}>
                      {char.status === 'Banned' && <i className="fas fa-ban"></i>}
                      {char.status === 'Active' && <i className="fas fa-check-circle"></i>}
                      {' '}{char.status}
                    </td>
                    <td style={{ padding: '12px', border: '1px solid #2a2a4e' }}>
                      <button style={{
                        padding: '6px 12px',
                        background: '#e94560',
                        border: 'none',
                        borderRadius: '4px',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontFamily: 'Cinzel, serif',
                        marginRight: '5px'
                      }}>
                        <i className="fas fa-edit"></i> Edit
                      </button>
                      <button style={{
                        padding: '6px 12px',
                        background: char.status === 'Banned' ? '#28a745' : '#dc3545',
                        border: 'none',
                        borderRadius: '4px',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontFamily: 'Cinzel, serif'
                      }}>
                        <i className={`fas fa-${char.status === 'Banned' ? 'unlock' : 'ban'}`}></i>
                        {' '}{char.status === 'Banned' ? 'Unban' : 'Ban'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GothicBox>

        <SkullDivider />

        {/* Typography Showcase */}
        <GothicBox style={{
          background: '#16213e',
          padding: '30px',
          borderRadius: '10px',
          marginBottom: '40px',
          textAlign: 'center'
        }}>
          <h1 style={{ fontFamily: 'Cinzel, serif', color: '#e94560', fontSize: '36px', marginBottom: '10px' }}>
            Cinzel Header Font - For Titles
          </h1>
          <p style={{ fontFamily: 'Crimson Text, serif', color: '#b5b5c3', fontSize: '20px', fontStyle: 'italic' }}>
            Crimson Text body font - For elegant, readable content that evokes gothic literature
          </p>
          <div style={{ marginTop: '30px' }}>
            <p style={{ color: '#e94560', fontSize: '24px', marginBottom: '10px' }}>
              <i className="fas fa-skull"></i> <i className="fas fa-ghost"></i> <i className="fas fa-bat"></i> <i className="fas fa-spider"></i> <i className="fas fa-crow"></i>
            </p>
            <p style={{ color: '#9d4edd', fontSize: '24px' }}>
              <i className="fas fa-wand-magic-sparkles"></i> <i className="fas fa-book-dead"></i> <i className="fas fa-candle-holder"></i> <i className="fas fa-hand-paper"></i> <i className="fas fa-dragon"></i>
            </p>
          </div>
        </GothicBox>

        {/* Footer */}
        <div style={{ 
          textAlign: 'center', 
          marginTop: '60px',
          padding: '30px',
          borderTop: '2px solid #2a2a4e'
        }}>
          <p style={{ 
            color: '#8b8b9f', 
            fontSize: '18px',
            fontFamily: 'Crimson Text, serif',
            fontStyle: 'italic'
          }}>
            "In the shadows we dwell, in blood we thrive, in darkness we rule..."
          </p>
          <div style={{ marginTop: '20px', fontSize: '14px', color: '#6a6a7f' }}>
            <i className="fas fa-moon"></i> ShadowRealms AI - Where Horror Meets Imagination <i className="fas fa-moon"></i>
          </div>
        </div>

      </div>
    </div>
  );
};

export default GothicShowcase;

