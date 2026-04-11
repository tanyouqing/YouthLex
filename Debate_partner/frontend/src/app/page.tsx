"use client";

import Link from "next/link";
import { ThemeToggle } from "../components/theme/ThemeToggle";
import { STATUTES_ARRAY } from "../utils/statutes";
import styles from "../styles/landing.module.css";
import React from 'react';

// Repeat array twice to guarantee seamless CSS infinite scroll visually
const repeatedStatutes = [...STATUTES_ARRAY, ...STATUTES_ARRAY];

function MarqueeTrack({ trackClass, reverse = false }: { trackClass: string, reverse?: boolean }) {
  // We randomly shuffle or slice the array for different tracks so they don't look identical
  const items = reverse ? [...repeatedStatutes].reverse() : repeatedStatutes;
  
  return (
    <div className={`${styles.marqueeTrack} ${trackClass}`}>
      {items.map((text, idx) => (
        <div key={idx} className={styles.pixelBox}>
          {text}
        </div>
      ))}
      {/* Duplicate for seamless looping */}
      {items.map((text, idx) => (
        <div key={`dup-${idx}`} className={styles.pixelBox}>
          {text}
        </div>
      ))}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className={styles.landingContainer}>
      {/* Top right theme toggle */}
      <div className={styles.themeControl}>
        <ThemeToggle />
      </div>

      {/* Background Marquee Tracks */}
      <div className={styles.marqueeOverlay}>
        <MarqueeTrack trackClass={styles.marqueeTrack1} />
        <MarqueeTrack trackClass={styles.marqueeTrack2} reverse />
        <MarqueeTrack trackClass={styles.marqueeTrack3} />
        <MarqueeTrack trackClass={styles.marqueeTrack4} reverse />
        <MarqueeTrack trackClass={styles.marqueeTrack5} />
      </div>

      {/* Foreground Content */}
      <main className={styles.centerContent}>
        <h1 className={styles.mainTitle}>
          <span className={styles.heroTitleEn}>
            <span className={styles.textYellow}>YOUTH</span>
            <span className={styles.textLex}>LEX</span>
          </span>
          <span className={styles.titleDash}>-</span>
          <span className={styles.heroTitleCn}>青律</span>
        </h1>
        <h2 className={styles.subTitle}>面向大学生的多功能维权智能体</h2>

        <div className={styles.actionGrid}>
          {/* 占位链接，指向当页或者后续开发的助手页 */}
          <div className={styles.actionWrap}>
            <Link href="#" className={styles.actionBtn}>
              维权小助手
            </Link>
            <div className={styles.hangingTag}>
              利益受到侵害却不知如何维权？
            </div>
          </div>
          
          {/* 指向刚才实现的辩论陪练功能 */}
          <div className={styles.actionWrap}>
            <Link href="/debate" className={styles.actionBtn}>
              辩论陪练
            </Link>
            <div className={styles.hangingTag}>
              搜集到了证据却不知如何应用？
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
