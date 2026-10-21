'use client';

import React, { useEffect, useRef } from 'react';

interface VoiceOrbProps {
  isActive: boolean;
  size?: number;
}

const N = 220;
const R = 1.0;

interface Particle {
  theta: number;
  phi: number;
  rOffset: number;
  size: number;
  baseAlpha: number;
}

export default function VoiceOrb({ isActive, size = 120 }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const tRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);

  useEffect(() => {
    // Build Fibonacci sphere once
    particlesRef.current = Array.from({ length: N }, (_, i) => {
      const theta = Math.acos(1 - 2 * (i + 0.5) / N);
      const phi = Math.PI * (1 + Math.sqrt(5)) * i;
      return {
        theta,
        phi,
        rOffset: (Math.random() - 0.5) * R * 0.12,
        size: Math.random() * 1.8 + 0.4,
        baseAlpha: Math.random() * 0.4 + 0.3,
      };
    });
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const scale = (size / 2) * 0.78;

    function draw() {
      if (!ctx) return;
      ctx.clearRect(0, 0, size, size);
      tRef.current += isActive ? 0.022 : 0.006;
      const t = tRef.current;

      const sinT = Math.sin(t * 0.4);
      const cosT = Math.cos(t * 0.4);

      // Collect projected points
      const pts = particlesRef.current.map((p) => {
        const r = R + p.rOffset + (isActive ? Math.sin(t * 2.5 + p.phi) * 0.06 : 0);
        const x = r * Math.sin(p.theta) * Math.cos(p.phi);
        const y = r * Math.sin(p.theta) * Math.sin(p.phi);
        const z = r * Math.cos(p.theta);

        // Rotate around Y axis
        const rx = x * cosT + z * sinT;
        const rz = -x * sinT + z * cosT;

        const px = cx + rx * scale;
        const py = cy + y * scale;
        const depth = (rz + R) / (2 * R); // 0..1 — front=1

        const alpha = p.baseAlpha + depth * 0.5 + (isActive ? 0.15 : 0);
        const dotSize = p.size * (0.5 + depth * 0.9) * (isActive ? 1.25 : 0.85);

        return { px, py, depth, alpha, dotSize };
      });

      // Sort back-to-front
      pts.sort((a, b) => a.depth - b.depth);

      pts.forEach(({ px, py, depth, alpha, dotSize }) => {
        const blue = Math.round(160 + depth * 95);
        const green = Math.round(80 + depth * 100);
        ctx.beginPath();
        ctx.arc(px, py, dotSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(30, ${green}, ${blue}, ${Math.min(alpha, 1)})`;
        ctx.fill();
      });

      // Glowing white core
      const coreAlpha = isActive ? 0.72 + Math.sin(t * 3) * 0.12 : 0.35;
      const coreR = isActive ? 7 + Math.sin(t * 4) * 2 : 5;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2.5);
      grad.addColorStop(0, `rgba(255, 255, 255, ${coreAlpha})`);
      grad.addColorStop(0.5, `rgba(130, 200, 255, ${coreAlpha * 0.4})`);
      grad.addColorStop(1, 'rgba(0, 80, 180, 0)');
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 2.5, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Outer glow ring when active
      if (isActive) {
        const ringAlpha = 0.12 + Math.sin(t * 2.1) * 0.06;
        const ring = ctx.createRadialGradient(cx, cy, scale * 0.7, cx, cy, scale * 1.1);
        ring.addColorStop(0, `rgba(0, 140, 255, ${ringAlpha})`);
        ring.addColorStop(1, 'rgba(0, 80, 200, 0)');
        ctx.beginPath();
        ctx.arc(cx, cy, scale * 1.1, 0, Math.PI * 2);
        ctx.fillStyle = ring;
        ctx.fill();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    draw();

    return () => {
      cancelAnimationFrame(animRef.current);
    };
  }, [isActive, size]);

  return (
    <canvas
      ref={canvasRef}
      style={{ display: 'block', borderRadius: '50%' }}
    />
  );
}
