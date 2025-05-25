export function fadeTransition(renderer) {
  const transitionObjects = new Set();
  
  // 添加过渡效果到对象
  function addTransitionEffect(object) {
    if (!object.userData) object.userData = {};
    object.userData.originalScale = object.scale.clone();
    object.userData.originalOpacity = object.material.opacity;
    transitionObjects.add(object);
  }

  // 执行过渡动画
  function animateTransition() {
    transitionObjects.forEach(object => {
      if (object.userData.transitioning) {
        const progress = object.userData.transitionProgress || 0;
        
        // 更新不透明度
        if (object.material.opacity !== undefined) {
          object.material.opacity = Math.sin(progress * Math.PI);
        }
        
        // 更新缩放
        const scale = 1 + Math.sin(progress * Math.PI) * 0.2;
        object.scale.set(
          object.userData.originalScale.x * scale,
          object.userData.originalScale.y * scale,
          object.userData.originalScale.z * scale
        );
        
        object.userData.transitionProgress += 0.02;
        if (object.userData.transitionProgress >= 1) {
          object.userData.transitioning = false;
          transitionObjects.delete(object);
        }
      }
    });
  }

  // 开始过渡
  function startTransition(object) {
    if (!object.userData) object.userData = {};
    object.userData.transitioning = true;
    object.userData.transitionProgress = 0;
    addTransitionEffect(object);
  }

  // 添加到渲染循环
  const originalRender = renderer.render;
  renderer.render = function(scene, camera) {
    animateTransition();
    originalRender.call(this, scene, camera);
  };

  return {
    startTransition,
    addTransitionEffect
  };
} 