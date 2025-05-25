const COLOR_MAPPING = {
  available: "green",
  occupied: "red",
  reserved: "yellow"
};

export default function SeatStatusBadge({ available, occupied, reserved }) {
  return (
    <div>
      <span style={{ color: COLOR_MAPPING.available }}>可用: {available}</span>
      <span style={{ color: COLOR_MAPPING.occupied }}>占用: {occupied}</span>
      <span style={{ color: COLOR_MAPPING.reserved }}>预约: {reserved}</span>
    </div>
  );
} 