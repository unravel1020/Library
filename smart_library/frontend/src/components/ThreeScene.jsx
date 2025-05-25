import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { fadeTransition } from '../threejs/fadeTransition';
import { saveAs } from 'file-saver';
import * as TWEEN from '@tweenjs/tween.js';

const WS_URL = 'ws://localhost:8080';
const ROWS = 5;
const COLS = 10;
const SEAT_SIZE = 0.4;
const SEAT_GAP = 0.6;
const TABLE_WIDTH = COLS * SEAT_GAP;
const TABLE_DEPTH = 0.5;
const ROOM_WIDTH = COLS * SEAT_GAP + 2;
const ROOM_DEPTH = ROWS * 2 + 2;
const ROOM_HEIGHT = 3;

// 书架配置
const BOOKSHELF_CONFIG = {
  width: 1.2,
  depth: 0.4,
  height: 2.2,
  gap: 0.8,
  rows: 2,
  cols: 4
};

// 讲台/服务台配置
const COUNTER_CONFIG = {
  width: 3,
  depth: 0.8,
  height: 1.1
};

const STATUS_COLOR = {
  available: '#00ff00', // 绿色
  occupied: '#ff0000', // 红色
  reserved: '#ffd600', // 黄色
  broken: '#888888'    // 灰色
};

// 预设视角配置
const CAMERA_PRESETS = {
  top: {
    position: new THREE.Vector3(0, ROOM_HEIGHT * 2, 0),
    lookAt: new THREE.Vector3(0, 0, 0)
  },
  front: {
    position: new THREE.Vector3(0, ROOM_HEIGHT/2, ROOM_DEPTH * 1.5),
    lookAt: new THREE.Vector3(0, ROOM_HEIGHT/2, 0)
  },
  side: {
    position: new THREE.Vector3(ROOM_WIDTH * 1.5, ROOM_HEIGHT/2, 0),
    lookAt: new THREE.Vector3(0, ROOM_HEIGHT/2, 0)
  },
  default: {
    position: new THREE.Vector3(0, ROOM_HEIGHT, ROOM_DEPTH/2 + 2),
    lookAt: new THREE.Vector3(0, 0, 0)
  }
};

// 在 useEffect 外部添加以下函数，确保全局可用
function onWindowResize() {
  // 这里假设 camera 和 renderer 是全局变量或通过 ref 获取
  // 你可以根据实际情况调整
  if (window.camera && window.renderer) {
    window.camera.aspect = window.innerWidth / window.innerHeight;
    window.camera.updateProjectionMatrix();
    window.renderer.setSize(window.innerWidth, window.innerHeight);
  }
}

export default function ThreeScene() {
  const mountRef = useRef();
  const seatMeshMap = useRef({});
  const sceneRef = useRef();
  const cameraRef = useRef();
  const transitionRef = useRef();
  const [selectedObject, setSelectedObject] = useState(null);
  const [hoveredObject, setHoveredObject] = useState(null);
  const [cameraMode, setCameraMode] = useState('orbit');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [showMiniMap, setShowMiniMap] = useState(true);
  const [sceneState, setSceneState] = useState(null);

  // animateCamera 提升到组件作用域
  function animateCamera(targetPosition, targetLookAt, duration = 1000) {
    const camera = cameraRef.current;
    if (!camera) return;
    const startPosition = camera.position.clone();
    const startLookAt = new THREE.Vector3();
    camera.getWorldDirection(startLookAt);
    startLookAt.multiplyScalar(10).add(camera.position);
    const startTime = Date.now();
    function updateCamera() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
      const currentLookAt = new THREE.Vector3();
      currentLookAt.lerpVectors(startLookAt, targetLookAt, easeProgress);
      camera.lookAt(currentLookAt);
      if (progress < 1) {
        requestAnimationFrame(updateCamera);
      }
    }
    updateCamera();
  }

  // saveSceneState 提升到组件作用域
  function saveSceneState() {
    const camera = cameraRef.current;
    const scene = sceneRef.current;
    if (!camera || !scene) return;
    const state = {
      camera: {
        position: camera.position.toArray(),
        lookAt: new THREE.Vector3().subVectors(
          camera.position,
          new THREE.Vector3().setFromMatrixColumn(camera.matrix, 2)
        ).toArray()
      },
      objects: scene.children
        .filter(obj => obj.userData && obj.userData.type)
        .map(obj => ({
          id: obj.userData.id,
          type: obj.userData.type,
          position: obj.position.toArray(),
          rotation: obj.rotation.toArray(),
          scale: obj.scale.toArray(),
          status: obj.userData.status,
          info: obj.userData.info
        }))
    };
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
    saveAs(blob, 'library-scene.json');
  }

  // loadSceneState 提升到组件作用域
  function loadSceneState(event) {
    const camera = cameraRef.current;
    const scene = sceneRef.current;
    if (!camera || !scene) return;
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const state = JSON.parse(e.target.result);
          if (state.camera) {
            const { position, lookAt } = state.camera;
            animateCamera(
              new THREE.Vector3(...position),
              new THREE.Vector3(...lookAt)
            );
          }
          state.objects.forEach(objState => {
            const obj = scene.children.find(
              child => child.userData && child.userData.id === objState.id
            );
            if (obj) {
              obj.position.fromArray(objState.position);
              obj.rotation.fromArray(objState.rotation);
              obj.scale.fromArray(objState.scale);
              obj.userData.status = objState.status;
              obj.userData.info = objState.info;
              if (obj.material && objState.status) {
                obj.material.color.set(STATUS_COLOR[objState.status]);
              }
            }
          });
          setSceneState(state);
        } catch (error) {
          console.error('Error loading scene state:', error);
          alert('加载场景状态失败');
        }
      };
      reader.readAsText(file);
    }
  }

  useEffect(() => {
    // 场景、相机、渲染器
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x22232a);
    sceneRef.current = scene;
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, ROOM_HEIGHT, ROOM_DEPTH/2 + 2);
    camera.lookAt(0, 0, 0);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    mountRef.current.appendChild(renderer.domElement);
    transitionRef.current = fadeTransition(renderer);

    // 添加轨道控制器
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 3;
    controls.maxDistance = 20;
    controls.maxPolarAngle = Math.PI / 2;

    // 灯光
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 5);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 50;
    dirLight.shadow.camera.left = -10;
    dirLight.shadow.camera.right = 10;
    dirLight.shadow.camera.top = 10;
    dirLight.shadow.camera.bottom = -10;
    scene.add(dirLight);

    // 为所有物体启用阴影
    scene.traverse((object) => {
      if (object.isMesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });

    // 地板
    const floorGeo = new THREE.BoxGeometry(ROOM_WIDTH, 0.1, ROOM_DEPTH);
    const floorMat = new THREE.MeshPhongMaterial({ color: 0xcccccc });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.position.set(0, -0.05, 0);
    scene.add(floor);

    // 墙壁
    const wallMat = new THREE.MeshPhongMaterial({ color: 0xeeeeee, side: THREE.DoubleSide });
    // 后墙
    const wallBack = new THREE.Mesh(new THREE.BoxGeometry(ROOM_WIDTH, ROOM_HEIGHT, 0.1), wallMat);
    wallBack.position.set(0, ROOM_HEIGHT/2, -ROOM_DEPTH/2);
    scene.add(wallBack);
    // 前墙（有门）
    const wallFront = new THREE.Mesh(new THREE.BoxGeometry(ROOM_WIDTH-2, ROOM_HEIGHT, 0.1), wallMat);
    wallFront.position.set(0, ROOM_HEIGHT/2, ROOM_DEPTH/2);
    scene.add(wallFront);
    // 左右墙（有窗）
    const wallLeft = new THREE.Mesh(new THREE.BoxGeometry(0.1, ROOM_HEIGHT, ROOM_DEPTH), wallMat);
    wallLeft.position.set(-ROOM_WIDTH/2, ROOM_HEIGHT/2, 0);
    scene.add(wallLeft);
    const wallRight = new THREE.Mesh(new THREE.BoxGeometry(0.1, ROOM_HEIGHT, ROOM_DEPTH), wallMat);
    wallRight.position.set(ROOM_WIDTH/2, ROOM_HEIGHT/2, 0);
    scene.add(wallRight);
    // 门
    const doorGeo = new THREE.BoxGeometry(1, 2, 0.12);
    const doorMat = new THREE.MeshPhongMaterial({ color: 0x8d5524 });
    const door = new THREE.Mesh(doorGeo, doorMat);
    door.position.set(0, 1, ROOM_DEPTH/2+0.06);
    scene.add(door);
    // 窗
    const windowGeo = new THREE.BoxGeometry(0.1, 1, 2);
    const windowMat = new THREE.MeshPhongMaterial({ color: 0x87ceeb, transparent: true, opacity: 0.5 });
    const window1 = new THREE.Mesh(windowGeo, windowMat);
    window1.position.set(-ROOM_WIDTH/2-0.06, 2, 0);
    scene.add(window1);
    const window2 = new THREE.Mesh(windowGeo, windowMat);
    window2.position.set(ROOM_WIDTH/2+0.06, 2, 0);
    scene.add(window2);

    // 添加书架
    const bookshelfMat = new THREE.MeshPhongMaterial({ color: 0x8B4513 });
    for (let row = 0; row < BOOKSHELF_CONFIG.rows; row++) {
      for (let col = 0; col < BOOKSHELF_CONFIG.cols; col++) {
        const bookshelf = new THREE.Mesh(
          new THREE.BoxGeometry(BOOKSHELF_CONFIG.width, BOOKSHELF_CONFIG.height, BOOKSHELF_CONFIG.depth),
          bookshelfMat
        );
        bookshelf.position.set(
          (col - (BOOKSHELF_CONFIG.cols-1)/2) * (BOOKSHELF_CONFIG.width + BOOKSHELF_CONFIG.gap),
          BOOKSHELF_CONFIG.height/2,
          -ROOM_DEPTH/2 + 0.5 + row * (BOOKSHELF_CONFIG.depth + 0.3)
        );
        bookshelf.userData = {
          type: 'bookshelf',
          id: `bookshelf-${row+1}-${col+1}`,
          info: {
            name: `书架 ${row+1}-${col+1}`,
            capacity: '约200本书',
            category: '综合类'
          }
        };
        scene.add(bookshelf);
      }
    }

    // 添加讲台/服务台
    const counterMat = new THREE.MeshPhongMaterial({ color: 0x4B0082 });
    const counter = new THREE.Mesh(
      new THREE.BoxGeometry(COUNTER_CONFIG.width, COUNTER_CONFIG.height, COUNTER_CONFIG.depth),
      counterMat
    );
    counter.position.set(0, COUNTER_CONFIG.height/2, ROOM_DEPTH/2 - 1);
    counter.userData = {
      type: 'counter',
      id: 'service-counter',
      info: {
        name: '服务台',
        description: '提供咨询、借还书等服务',
        staff: '2名工作人员'
      }
    };
    scene.add(counter);

    // 桌椅和座位
    for (let row = 0; row < ROWS; row++) {
      // 桌子
      const tableGeo = new THREE.BoxGeometry(TABLE_WIDTH, 0.1, TABLE_DEPTH);
      const tableMat = new THREE.MeshPhongMaterial({ color: 0xf5deb3 });
      const table = new THREE.Mesh(tableGeo, tableMat);
      table.position.set(0, 0.5, (row - (ROWS-1)/2) * 2);
      scene.add(table);
      // 座位
      for (let col = 0; col < COLS; col++) {
        // 椅子
        const chairGeo = new THREE.CylinderGeometry(SEAT_SIZE/2, SEAT_SIZE/2, 0.18, 16);
        const chairMat = new THREE.MeshPhongMaterial({ color: 0x444444 });
        const chair = new THREE.Mesh(chairGeo, chairMat);
        chair.position.set(
          (col - (COLS-1)/2) * SEAT_GAP,
          0.09,
          (row - (ROWS-1)/2) * 2 - TABLE_DEPTH/2 - 0.3
        );
        scene.add(chair);
        // 座位（可变色）
        const seatGeo = new THREE.SphereGeometry(SEAT_SIZE/2, 16, 16);
        const seatMat = new THREE.MeshPhongMaterial({ color: STATUS_COLOR.available });
        const seat = new THREE.Mesh(seatGeo, seatMat);
        seat.position.set(
          (col - (COLS-1)/2) * SEAT_GAP,
          0.25,
          (row - (ROWS-1)/2) * 2 - TABLE_DEPTH/2 - 0.3
        );
        seat.userData = {
          type: 'seat',
          id: `seat-${row+1}-${col+1}`,
          status: 'available',
          info: {
            name: `座位 ${row+1}-${col+1}`,
            type: '普通座位',
            hasPower: true,
            hasComputer: false
          }
        };
        scene.add(seat);
        seatMeshMap.current[seat.userData.id] = seat;
      }
    }

    // 添加场景标签
    const labelDiv = document.createElement('div');
    labelDiv.style.position = 'absolute';
    labelDiv.style.pointerEvents = 'none';
    labelDiv.style.color = 'white';
    labelDiv.style.fontSize = '14px';
    labelDiv.style.fontFamily = 'Arial';
    labelDiv.style.textShadow = '1px 1px 1px black';
    mountRef.current.appendChild(labelDiv);

    // 创建标签位置映射
    const labelPositions = new Map();
    function updateLabelPosition(object, label) {
      const vector = object.position.clone();
      vector.project(camera);
      const x = (vector.x * 0.5 + 0.5) * window.innerWidth;
      const y = (-vector.y * 0.5 + 0.5) * window.innerHeight;
      label.style.transform = `translate(-50%, -50%) translate(${x}px,${y}px)`;
    }

    // 为每个物体添加标签
    function addLabel(object) {
      if (object.userData && object.userData.info) {
        const label = document.createElement('div');
        label.textContent = object.userData.info.name;
        label.style.opacity = '0';
        label.style.transition = 'opacity 0.3s';
        labelDiv.appendChild(label);
        labelPositions.set(object, label);
      }
    }

    // 交互：鼠标悬停和点击
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const originalMaterials = new Map();

    function onMouseMove(event) {
      // 计算鼠标在归一化设备坐标中的位置
      mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

      // 更新射线
      raycaster.setFromCamera(mouse, camera);

      // 获取射线与物体的交点
      const intersects = raycaster.intersectObjects(scene.children);

      // 重置之前高亮的物体
      if (hoveredObject) {
        const originalMaterial = originalMaterials.get(hoveredObject);
        if (originalMaterial) {
          hoveredObject.material = originalMaterial;
        }
        setHoveredObject(null);
      }

      // 高亮当前悬停的物体
      if (intersects.length > 0) {
        const object = intersects[0].object;
        if (object.userData && (object.userData.type === 'seat' || object.userData.type === 'bookshelf' || object.userData.type === 'counter')) {
          if (!originalMaterials.has(object)) {
            originalMaterials.set(object, object.material.clone());
          }
          const highlightMaterial = object.material.clone();
          highlightMaterial.emissive = new THREE.Color(0x666666);
          object.material = highlightMaterial;
          setHoveredObject(object);
        }
      }
    }

    function onClick(event) {
      // 计算鼠标在归一化设备坐标中的位置
      mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

      // 更新射线
      raycaster.setFromCamera(mouse, camera);

      // 获取射线与物体的交点
      const intersects = raycaster.intersectObjects(scene.children);

      if (intersects.length > 0) {
        const object = intersects[0].object;
        if (object.userData && (object.userData.type === 'seat' || object.userData.type === 'bookshelf' || object.userData.type === 'counter')) {
          setSelectedObject(object.userData);
        }
      } else {
        setSelectedObject(null);
      }
    }

    // 添加事件监听器
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('click', onClick);

    // 更新标签可见性
    function updateLabels() {
      labelPositions.forEach((label, object) => {
        const vector = object.position.clone();
        vector.project(camera);
        if (vector.z < 1) {
          updateLabelPosition(object, label);
          label.style.opacity = '1';
        } else {
          label.style.opacity = '0';
        }
      });
    }

    // 添加动画效果
    function animateObjects() {
      scene.children.forEach(object => {
        if (object.userData && object.userData.type) {
          // 添加轻微的浮动动画
          object.position.y += Math.sin(Date.now() * 0.001 + object.position.x) * 0.0001;
        }
      });
    }

    // 添加阴影
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 创建小地图
    const miniMapCamera = new THREE.OrthographicCamera(
      -ROOM_WIDTH/2, ROOM_WIDTH/2,
      ROOM_DEPTH/2, -ROOM_DEPTH/2,
      0.1, 1000
    );
    miniMapCamera.position.set(0, ROOM_HEIGHT * 2, 0);
    miniMapCamera.lookAt(0, 0, 0);

    const miniMapRenderer = new THREE.WebGLRenderer({ antialias: true });
    miniMapRenderer.setSize(200, 200);
    miniMapRenderer.shadowMap.enabled = true;
    miniMapRenderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const miniMapDiv = document.createElement('div');
    miniMapDiv.style.position = 'absolute';
    miniMapDiv.style.bottom = '20px';
    miniMapDiv.style.right = '20px';
    miniMapDiv.style.width = '200px';
    miniMapDiv.style.height = '200px';
    miniMapDiv.style.border = '2px solid white';
    miniMapDiv.style.borderRadius = '4px';
    miniMapDiv.style.overflow = 'hidden';
    miniMapDiv.appendChild(miniMapRenderer.domElement);
    mountRef.current.appendChild(miniMapDiv);

    // 相机动画
    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      animateObjects();
      updateLabels();
      renderer.render(scene, camera);
      
      // 更新小地图
      if (showMiniMap) {
        miniMapRenderer.render(scene, miniMapCamera);
      }
    }
    animate();

    // 添加物体状态变化动画
    function animateObjectState(object, newState) {
      if (!object.userData) return;
      
      const originalScale = object.scale.clone();
      const targetScale = originalScale.clone().multiplyScalar(1.2);
      
      // 缩放动画
      const scaleAnimation = new TWEEN.Tween(object.scale)
        .to({ x: targetScale.x, y: targetScale.y, z: targetScale.z }, 200)
        .easing(TWEEN.Easing.Quadratic.Out)
        .yoyo(true)
        .repeat(1);
      
      // 颜色变化动画
      if (object.material) {
        const originalColor = object.material.color.clone();
        const targetColor = new THREE.Color(STATUS_COLOR[newState] || '#ffffff');
        
        const colorAnimation = new TWEEN.Tween(object.material.color)
          .to({ r: targetColor.r, g: targetColor.g, b: targetColor.b }, 400)
          .easing(TWEEN.Easing.Quadratic.InOut);
        
        colorAnimation.start();
      }
      
      scaleAnimation.start();
    }

    cameraRef.current = camera;

    // 修改清理函数
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('click', onClick);
      window.removeEventListener('resize', onWindowResize);
      mountRef.current.removeChild(renderer.domElement);
      mountRef.current.removeChild(labelDiv);
      mountRef.current.removeChild(miniMapDiv);
      controls.dispose();
    };
  }, []);

  // 处理视角切换
  const handleViewChange = (view) => {
    const preset = CAMERA_PRESETS[view];
    if (preset) {
      animateCamera(preset.position, preset.lookAt);
    }
  };

  // 处理搜索
  const handleSearch = (query) => {
    setSearchQuery(query);
    // 实现搜索逻辑
  };

  // 处理分类筛选
  const handleCategoryChange = (category) => {
    setSelectedCategory(category);
    // 实现分类筛选逻辑
  };

  return (
    <div style={{ position: 'relative' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100vh' }} />
      
      {/* 控制面板 */}
      <div style={{
        position: 'absolute',
        top: '20px',
        right: '20px',
        background: 'rgba(255, 255, 255, 0.9)',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        {/* 视角控制 */}
        <div>
          <h4 style={{ margin: '0 0 10px 0' }}>视角控制</h4>
          <div style={{ display: 'flex', gap: '5px' }}>
            <button onClick={() => handleViewChange('top')}>俯视图</button>
            <button onClick={() => handleViewChange('front')}>前视图</button>
            <button onClick={() => handleViewChange('side')}>侧视图</button>
            <button onClick={() => handleViewChange('default')}>默认视角</button>
          </div>
        </div>

        {/* 搜索框 */}
        <div>
          <input
            type="text"
            placeholder="搜索..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            style={{
              padding: '8px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              width: '100%'
            }}
          />
        </div>

        {/* 分类筛选 */}
        <div>
          <select
            value={selectedCategory}
            onChange={(e) => handleCategoryChange(e.target.value)}
            style={{
              padding: '8px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              width: '100%'
            }}
          >
            <option value="all">所有</option>
            <option value="seat">座位</option>
            <option value="bookshelf">书架</option>
            <option value="counter">服务台</option>
          </select>
        </div>

        {/* 小地图控制 */}
        <div>
          <label>
            <input
              type="checkbox"
              checked={showMiniMap}
              onChange={(e) => setShowMiniMap(e.target.checked)}
            />
            显示小地图
          </label>
        </div>

        {/* 视角模式切换 */}
        <button
          onClick={() => setCameraMode(mode => mode === 'orbit' ? 'fixed' : 'orbit')}
          style={{
            padding: '8px 16px',
            border: 'none',
            borderRadius: '4px',
            background: '#4CAF50',
            color: 'white',
            cursor: 'pointer'
          }}
        >
          {cameraMode === 'orbit' ? '固定视角' : '自由视角'}
        </button>

        {/* 场景状态控制 */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={saveSceneState}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '4px',
              background: '#2196F3',
              color: 'white',
              cursor: 'pointer',
              flex: 1
            }}
          >
            保存场景
          </button>
          <label
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '4px',
              background: '#FF9800',
              color: 'white',
              cursor: 'pointer',
              textAlign: 'center',
              flex: 1
            }}
          >
            加载场景
            <input
              type="file"
              accept=".json"
              onChange={loadSceneState}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </div>

      {/* 信息弹窗 */}
      {selectedObject && (
        <div style={{
          position: 'absolute',
          top: '20px',
          left: '20px',
          background: 'rgba(255, 255, 255, 0.9)',
          padding: '20px',
          borderRadius: '8px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
          maxWidth: '300px'
        }}>
          <h3>{selectedObject.info.name}</h3>
          {Object.entries(selectedObject.info).map(([key, value]) => (
            key !== 'name' && (
              <p key={key}>
                <strong>{key}: </strong>
                {value}
              </p>
            )
          ))}
          <button
            onClick={() => setSelectedObject(null)}
            style={{
              position: 'absolute',
              top: '10px',
              right: '10px',
              background: 'none',
              border: 'none',
              fontSize: '20px',
              cursor: 'pointer'
            }}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
} 