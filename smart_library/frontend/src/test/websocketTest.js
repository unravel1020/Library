// WebSocket 测试脚本
const ws = new WebSocket('ws://localhost:8080');

// 测试数据
const testData = [
  {
    id: "library1",
    type: "cube",
    x: 0,
    y: 0,
    z: 0,
    color: "#ff0000",
    size: 2
  },
  {
    id: "library2",
    type: "sphere",
    x: 3,
    y: 0,
    z: 0,
    color: "#00ff00",
    size: 1.5
  }
];

// 连接建立后发送初始数据
ws.onopen = () => {
  console.log('WebSocket 连接已建立');
  ws.send(JSON.stringify(testData));
};

// 模拟数据更新
setInterval(() => {
  // 随机更新位置
  const updatedData = testData.map(obj => ({
    ...obj,
    x: obj.x + (Math.random() - 0.5) * 0.5,
    y: obj.y + (Math.random() - 0.5) * 0.5,
    z: obj.z + (Math.random() - 0.5) * 0.5
  }));
  
  ws.send(JSON.stringify(updatedData));
}, 2000);

// 模拟添加/删除对象
setInterval(() => {
  if (testData.length > 1) {
    testData.pop(); // 删除最后一个对象
  } else {
    testData.push({
      id: "library" + (testData.length + 1),
      type: Math.random() > 0.5 ? "cube" : "sphere",
      x: Math.random() * 6 - 3,
      y: Math.random() * 6 - 3,
      z: Math.random() * 6 - 3,
      color: "#" + Math.floor(Math.random()*16777215).toString(16),
      size: 1 + Math.random()
    });
  }
  ws.send(JSON.stringify(testData));
}, 5000); 