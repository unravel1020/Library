import React from 'react';
import SeatStatusBadge from './components/SeatStatusBadge';
import ThreeScene from './components/ThreeScene';

function App() {
  return (
    <div>
      <h1>Smart Library Digital Twin</h1>
      <SeatStatusBadge available={10} occupied={5} reserved={3} />
      <ThreeScene />
    </div>
  );
}

export default App; 