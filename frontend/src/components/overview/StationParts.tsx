import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
export function PrintedLabel({
  text,
  position,
  rotation = [0, 0, 0],
  width = 1.2,
  height = 0.3,
  color = "white",
}: {
  text: string;
  position: [number, number, number];
  rotation?: [number, number, number];
  width?: number;
  height?: number;
  color?: string;
}) {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    if (context) {
      context.clearRect(0, 0, 512, 128);
      context.fillStyle = color;
      context.font = "bold 60px Arial";
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(text, 256, 64, 480);
    }
    const map = new THREE.CanvasTexture(canvas);
    map.colorSpace = THREE.SRGBColorSpace;
    return map;
  }, [text, color]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={[width, height]} />
      <meshBasicMaterial
        map={texture}
        transparent
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}
export interface SensorComponentProps {
  isActive: boolean;
  onClick: () => void;
  position?: [number, number, number];
}
interface RotatingSensorProps extends SensorComponentProps {
  isRotating: boolean;
  speed?: number;
  direction?: number;
}
export function BaseBoard({ isActive, onClick }: SensorComponentProps) {
  return (
    <mesh
      position={[0, 0, 0.5]}
      receiveShadow
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <boxGeometry args={[9.2, 0.3, 5.4]} />
      <meshStandardMaterial
        color={isActive ? "#d5e8b8" : "#ddd9bf"}
        roughness={0.6}
        metalness={0.2}
      />
    </mesh>
  );
}

export function Structure() {
  return (
    <group>
      {                        }
      <mesh position={[0, 1.5, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.1, 3]} />
        <meshStandardMaterial color="#D1D5DB" metalness={0.9} roughness={0.1} />
      </mesh>
      {                 }
      <mesh position={[0, 0.1, 0]}>
        <cylinderGeometry args={[0.35, 0.35, 0.1]} />
        <meshStandardMaterial color="#9CA3AF" metalness={0.45} />
      </mesh>
      {                    }
      <mesh position={[0, 3, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.1, 0.1, 6]} />
        <meshStandardMaterial color="#D1D5DB" metalness={0.9} roughness={0.1} />
      </mesh>
      {                }
      <mesh position={[0, 3, 0]}>
        <sphereGeometry args={[0.22]} />
        <meshStandardMaterial color="#9CA3AF" metalness={0.45} />
      </mesh>
      {                 }
      <mesh position={[-2.5, 3, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.18, 0.18, 0.4]} />
        <meshStandardMaterial color="#9CA3AF" />
      </mesh>
      <mesh position={[2.5, 3, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.18, 0.18, 0.4]} />
        <meshStandardMaterial color="#9CA3AF" />
      </mesh>
    </group>
  );
}

export function WindVane({
  position,
  isActive,
  isRotating,
  speed = 1,
  direction = 0,
  onClick,
}: RotatingSensorProps) {
  const group = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    if (isRotating && group.current) {
      group.current.rotation.y = THREE.MathUtils.damp(
        group.current.rotation.y,
        direction,
        3,
        delta,
      );
    }
  });

  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {                   }
      <mesh position={[0, -0.2, 0]}>
        <cylinderGeometry args={[0.35, 0.35, 0.6]} />
        <meshStandardMaterial
          color={isActive ? "#60a5fa" : "#F9FAFB"}
          metalness={0.5}
          roughness={0.2}
        />
      </mesh>
      <PrintedLabel
        text="N"
        position={[0, -0.2, 0.36]}
        width={0.3}
        height={0.3}
        color="#1d4ed8"
      />

      {                   }
      <group ref={group}>
        <mesh position={[0, 0.3, 0]}>
          <cylinderGeometry args={[0.2, 0.2, 0.6]} />
          <meshStandardMaterial color="#F3F4F6" />
        </mesh>
        {                 }
        <mesh position={[0, 0.6, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.05, 0.05, 1.2]} />
          <meshStandardMaterial color="#111827" />
        </mesh>
        {                }
        <mesh position={[0, 0.6, 0.6]} rotation={[Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.12, 0.3, 8]} />
          <meshStandardMaterial color="#111827" />
        </mesh>
        {               }
        <mesh position={[0, 0.8, -0.6]}>
          <boxGeometry args={[0.04, 0.5, 0.5]} />
          <meshStandardMaterial color="#111827" />
        </mesh>
      </group>
    </group>
  );
}

export function Anemometer({
  position,
  isActive,
  isRotating,
  speed = 1,
  direction = 0,
  onClick,
}: RotatingSensorProps) {
  const group = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    if (isRotating && group.current) {
      group.current.rotation.y += delta * Math.min(speed * 0.3, 10);
    }
  });

  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <mesh position={[0, -0.2, 0]}>
        <cylinderGeometry args={[0.3, 0.3, 0.6]} />
        <meshStandardMaterial
          color={isActive ? "#60a5fa" : "#F9FAFB"}
          metalness={0.5}
          roughness={0.2}
        />
      </mesh>

      <group ref={group} position={[0, 0.4, 0]}>
        <mesh>
          <cylinderGeometry args={[0.25, 0.25, 0.4]} />
          <meshStandardMaterial color="#F3F4F6" />
        </mesh>

        {            }
        {[0, 1, 2].map((i) => (
          <group key={i} rotation={[0, (i * Math.PI * 2) / 3, 0]}>
            <mesh position={[0.6, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.05, 0.05, 1.2]} />
              <meshStandardMaterial color="#374151" />
            </mesh>
            <mesh position={[1.2, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
              <sphereGeometry args={[0.3, 32, 32, 0, Math.PI]} />
              <meshStandardMaterial
                color="#FFFFFF"
                side={THREE.DoubleSide}
                roughness={0.28}
              />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}

export function RainGauge({
  position,
  isActive,
  onClick,
}: SensorComponentProps) {
  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {               }
      <mesh castShadow>
        <cylinderGeometry args={[0.6, 0.6, 1.2, 32]} />
        <meshStandardMaterial
          color={isActive ? "#60a5fa" : "#FDFDFD"}
          metalness={0.05}
          roughness={0.1}
        />
      </mesh>
      {                }
      <mesh position={[0, 0.65, 0]} castShadow>
        <cylinderGeometry args={[0.7, 0.6, 0.3, 32]} />
        <meshStandardMaterial color="#F9FAFB" />
      </mesh>
      {                 }
      <mesh position={[0, 0.75, 0]}>
        <cylinderGeometry args={[0.65, 0.65, 0.02, 32]} />
        <meshStandardMaterial color="#000000" />
      </mesh>
    </group>
  );
}

export function Controller({
  position,
  isActive,
  onClick,
}: SensorComponentProps) {
  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {         }
      <mesh castShadow>
        <boxGeometry args={[1, 0.1, 1.2]} />
        <meshStandardMaterial
          color={isActive ? "#4ade80" : "#1B4332"}
          roughness={0.4}
        />
      </mesh>
      {                }
      <mesh position={[0.25, 0.2, 0.25]}>
        <boxGeometry args={[0.4, 0.25, 0.4]} />
        <meshStandardMaterial color="#0F172A" />
      </mesh>
      <mesh position={[-0.25, 0.2, -0.35]}>
        <boxGeometry args={[0.3, 0.25, 0.5]} />
        <meshStandardMaterial color="#334155" />
      </mesh>
      {                                                 }
      {[-0.4, -0.2, 0, 0.2, 0.4].map((x) => (
        <group key={x}>
          <mesh position={[x, 0.12, 0.48]}>
            <boxGeometry args={[0.06, 0.14, 0.08]} />
            <meshStandardMaterial color="#c4b581" metalness={0.5} />
          </mesh>
          <mesh position={[x, 0.12, -0.48]}>
            <boxGeometry args={[0.06, 0.14, 0.08]} />
            <meshStandardMaterial color="#c4b581" metalness={0.5} />
          </mesh>
          <mesh position={[x, 0.061, 0]}>
            <boxGeometry args={[0.012, 0.006, 0.8]} />
            <meshStandardMaterial color="#54846b" />
          </mesh>
        </group>
      ))}
      {                }
      <mesh position={[-0.3, 0.2, 0.3]}>
        <sphereGeometry args={[0.06]} />
        <meshStandardMaterial
          color="#2ECC71"
          emissive="#2ECC71"
          emissiveIntensity={4}
        />
      </mesh>
    </group>
  );
}

export function LCD({
  position,
  isActive,
  onClick,
  reading = "NO SIGNAL",
}: SensorComponentProps & { reading?: string }) {
  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {          }
      <mesh castShadow>
        <boxGeometry args={[1.6, 0.4, 0.9]} />
        <meshStandardMaterial color="#1E293B" metalness={0.5} roughness={0.2} />
      </mesh>
      {            }
      <mesh position={[0, 0.22, 0]}>
        <boxGeometry args={[1.3, 0.05, 0.65]} />
        <meshStandardMaterial
          color={isActive ? "#2ECC71" : "#2563EB"}
          emissive={isActive ? "#2ECC71" : "#1D4ED8"}
          emissiveIntensity={isActive ? 5 : 2}
        />
      </mesh>
      <PrintedLabel
        text={reading}
        position={[0, 0.3, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        width={1.2}
        height={0.32}
      />
    </group>
  );
}

export function SolarPanel({
  position,
  isActive,
  onClick,
}: SensorComponentProps) {
  return (
    <group
      position={position}
      rotation={[-0.35, 0, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {           }
      <mesh castShadow>
        <boxGeometry args={[1.8, 0.12, 1.8]} />
        <meshStandardMaterial color="#1F2937" metalness={0.9} roughness={0.1} />
      </mesh>
      {           }
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[1.65, 0.02, 1.65]} />
        <meshStandardMaterial
          color={isActive ? "#60A5FA" : "#234e73"}
          metalness={0.45}
          roughness={0.28}
        />
      </mesh>
      {                }
      <group position={[0, 0.12, 0]}>
        {[-0.5, -0.25, 0, 0.25, 0.5].map((x) => (
          <mesh key={`h-${x}`} position={[x, 0, 0]}>
            <boxGeometry args={[0.015, 0.015, 1.65]} />
            <meshStandardMaterial color="#475569" />
          </mesh>
        ))}
        {[-0.5, -0.25, 0, 0.25, 0.5].map((z) => (
          <mesh key={`v-${z}`} position={[0, 0, z]}>
            <boxGeometry args={[1.65, 0.015, 0.015]} />
            <meshStandardMaterial color="#475569" />
          </mesh>
        ))}
      </group>
    </group>
  );
}

export function SoilMoisture({
  position,
  isActive,
  onClick,
}: SensorComponentProps) {
  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {                }
      <mesh position={[0, -0.1, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[1.2, 64]} />
        <meshStandardMaterial color="#302015" roughness={1} />
      </mesh>
      {                       }
      <mesh position={[0, 0.08, 0]}>
        <sphereGeometry args={[0.5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#402D20" roughness={1} />
      </mesh>
      {                   }
      <mesh position={[0, 1.3, 0]} castShadow>
        <cylinderGeometry args={[0.12, 0.12, 1]} />
        <meshStandardMaterial
          color={isActive ? "#60a5fa" : "#1E293B"}
          roughness={0.2}
          metalness={0.3}
        />
      </mesh>
      {           }
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.04, 0.04, 1.8]} />
        <meshStandardMaterial color="#F3F4F6" metalness={0.45} roughness={0} />
      </mesh>
    </group>
  );
}
