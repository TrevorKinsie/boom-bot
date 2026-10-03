/**
 * Ambient declarations for the vendored three.js r128 *global* build
 * (`lib/three.min.js` + `lib/OrbitControls.js`, both non-module scripts that
 * populate the `THREE` namespace). We declare only the surface the client
 * actually uses so `tsc --strict` still catches property/constructor mistakes.
 */

declare namespace THREE {
  interface Vec3 {
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number): void;
  }

  class Object3D {
    position: Vec3;
    rotation: Vec3;
    scale: Vec3 & { setScalar(n: number): void };
    visible: boolean;
    add(child: Object3D): void;
    remove(child: Object3D): void;
  }

  class Color {
    constructor(hex?: number);
    setHSL(h: number, s: number, l: number): Color;
    getHexString(): string;
  }

  class Fog {
    constructor(color: number, near: number, far: number);
  }

  class Vector3 implements Vec3 {
    constructor(x?: number, y?: number, z?: number);
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number): void;
  }

  class PerspectiveCamera extends Object3D {
    constructor(fov: number, aspect: number, near: number, far: number);
    aspect: number;
    updateProjectionMatrix(): void;
  }

  class AmbientLight extends Object3D {
    constructor(color: number, intensity: number);
  }

  class DirectionalLight extends Object3D {
    constructor(color: number, intensity: number);
  }

  class WebGLRenderer {
    constructor(options?: { antialias?: boolean });
    domElement: HTMLCanvasElement;
    shadowMap: { enabled: boolean };
    setPixelRatio(ratio: number): void;
    setSize(width: number, height: number): void;
    render(scene: Scene, camera: PerspectiveCamera): void;
  }

  class OrbitControls {
    constructor(camera: PerspectiveCamera, domElement: HTMLElement);
    target: Vec3;
    enableDamping: boolean;
    maxPolarAngle: number;
    update(): void;
  }

  interface MaterialOptions {
    color?: string | number;
    flatShading?: boolean;
    transparent?: boolean;
    opacity?: number;
    map?: object;
    depthTest?: boolean;
  }

  class MeshLambertMaterial {
    constructor(options?: MaterialOptions);
  }

  class PlaneGeometry {
    constructor(width: number, height: number);
  }

  class BoxGeometry {
    constructor(width: number, height: number, depth: number);
  }

  class ConeGeometry {
    constructor(radius: number, height: number, segments: number);
  }

  class IcosahedronGeometry {
    constructor(radius: number, detail: number);
  }

  class SphereGeometry {
    constructor(radius: number, widthSegments: number, heightSegments: number);
  }

  class CylinderGeometry {
    constructor(
      rTop: number,
      rBottom: number,
      height: number,
      segments: number,
    );
  }

  class Scene extends Object3D {
    background: Color;
    fog: Fog | null;
  }

  class Mesh extends Object3D {
    constructor(geometry: object, material: MeshLambertMaterial);
  }

  class Group extends Object3D {}

  class Sprite extends Object3D {
    constructor(material: SpriteMaterial);
  }

  class SpriteMaterial {
    constructor(options?: MaterialOptions);
  }

  class CanvasTexture {
    constructor(canvas: HTMLCanvasElement);
  }

  class Raycaster {
    setFromCamera(
      coords: { x: number; y: number },
      camera: PerspectiveCamera,
    ): void;
    ray: Ray;
  }

  class Ray {
    intersectPlane(plane: Plane, target: Vec3): Vec3 | null;
  }

  class Plane {
    constructor(normal: Vec3, constant: number);
  }
}
