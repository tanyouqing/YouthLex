import { useEffect, useRef } from "react";

export function useAutoScroll(dependency: any) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      const element = scrollRef.current;
      element.scrollTop = element.scrollHeight;
    }
  }, [dependency]);

  return scrollRef;
}
