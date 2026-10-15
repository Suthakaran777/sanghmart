import React from 'react';

/**
 * BhagwaDhwaj (Sacred Saffron Double-Pennant Flag)
 * Authentic SVG representation of the Bhagwa Dhwaj.
 */
export default function BhagwaDhwaj({
  size = 32,
  animated = false,
  className = '',
  style = {}
}) {
  // viewBox: 0 0 100 100
  return (
    <div
      className={`bhagwa-dhwaj-container ${animated ? 'bhagwa-flag-flutter' : ''} ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: `${size}px`,
        height: `${size}px`,
        ...style
      }}
    >
      <svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          filter: animated ? 'drop-shadow(0 10px 25px rgba(234, 88, 12, 0.28))' : 'drop-shadow(0 2px 5px rgba(217, 83, 30, 0.2))',
          overflow: 'visible'
        }}
      >
        <defs>
          {/* Main Bhagwa Saffron Gradient */}
          <linearGradient id="bhagwaGrad" x1="14" y1="14" x2="88" y2="72" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ff7a00" />
            <stop offset="45%" stopColor="#ea580c" />
            <stop offset="100%" stopColor="#c2410c" />
          </linearGradient>

          {/* Saffron Highlights / Silk Fold Sheen */}
          <linearGradient id="bhagwaHighlight" x1="14" y1="20" x2="85" y2="35" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffa040" stopOpacity="0.85" />
            <stop offset="60%" stopColor="#ea580c" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#9a3412" stopOpacity="0.7" />
          </linearGradient>

          {/* Golden Finial & Brass Trim */}
          <linearGradient id="goldFinial" x1="12" y1="3" x2="16" y2="15" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#fef08a" />
            <stop offset="40%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#a16207" />
          </linearGradient>

          {/* Wooden / Polished Staff Gradient */}
          <linearGradient id="staffGrad" x1="12" y1="10" x2="16" y2="95" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#d97706" />
            <stop offset="50%" stopColor="#78350f" />
            <stop offset="100%" stopColor="#451a03" />
          </linearGradient>
        </defs>

        {/* --- FLAG STAFF (Danda) --- */}
        {/* Main Shaft */}
        <rect x="12" y="10" width="3.5" height="85" rx="1.5" fill="url(#staffGrad)" />
        <rect x="12.5" y="10" width="1" height="85" fill="#fde68a" opacity="0.3" />

        {/* Bottom Staff Ring / Base */}
        <circle cx="13.75" cy="94" r="2.5" fill="#ca8a04" />

        {/* Top Finial (Kalash / Spear Finial) */}
        <path
          d="M 13.75 2 
             C 16.5 6, 17 9, 13.75 11 
             C 10.5 9, 11 6, 13.75 2 Z"
          fill="url(#goldFinial)"
          stroke="#ca8a04"
          strokeWidth="0.5"
        />
        {/* Finial Base Ring */}
        <ellipse cx="13.75" cy="11" rx="3.5" ry="1.5" fill="#eab308" stroke="#a16207" strokeWidth="0.5" />

        {/* --- BHAGWA DHWAJ DOUBLE PENNANT (PATAKA) --- */}
        {/*
          Iconic double-triangular swallowtail RSS Bhagwa Dhwaj:
          Starts at staff (14, 15) -> Top tip (88, 29) -> Middle inner notch (36, 44) ->
          Bottom tip (88, 59) -> Bottom hoist (14, 73) -> Closed at hoist (14, 15).
        */}
        <path
          className="bhagwa-cloth"
          d="M 14.5 15.5
             Q 45 19, 87 29.5
             Q 58 37, 36 44.5
             Q 58 52, 87 59.5
             Q 45 66.5, 14.5 73.5
             Z"
          fill="url(#bhagwaGrad)"
          stroke="#9a3412"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />

        {/* Top Pennant Upper Fold Highlight */}
        <path
          d="M 14.5 16.5
             Q 45 20, 85 29.5
             L 36 44
             Z"
          fill="url(#bhagwaHighlight)"
          opacity="0.6"
        />

        {/* Lower Pennant Shading */}
        <path
          d="M 36 44.5
             L 86 59.5
             Q 45 66.5, 14.5 73
             Z"
          fill="#9a3412"
          opacity="0.18"
        />

        {/* Wind Crease / Wave Lines for Natural Flutter Depth */}
        <path
          d="M 14.5 15.5 Q 48 30, 87 29.5"
          stroke="#fed7aa"
          strokeWidth="0.8"
          strokeLinecap="round"
          opacity="0.45"
        />
        <path
          d="M 36 44.5 Q 55 52, 87 59.5"
          stroke="#fed7aa"
          strokeWidth="0.8"
          strokeLinecap="round"
          opacity="0.35"
        />

        {/* Hoist Ties / Golden Ribbons attaching flag to pole */}
        <rect x="11.5" y="18" width="5.5" height="2.5" rx="1" fill="#fde047" stroke="#ca8a04" strokeWidth="0.5" />
        <rect x="11.5" y="43" width="5.5" height="2.5" rx="1" fill="#fde047" stroke="#ca8a04" strokeWidth="0.5" />
        <rect x="11.5" y="68" width="5.5" height="2.5" rx="1" fill="#fde047" stroke="#ca8a04" strokeWidth="0.5" />
      </svg>
    </div>
  );
}
