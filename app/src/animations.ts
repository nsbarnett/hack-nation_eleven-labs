export const contentTransition = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.24 },
};
export const orbSpring = {
  type: "spring" as const,
  stiffness: 420,
  damping: 32,
};
