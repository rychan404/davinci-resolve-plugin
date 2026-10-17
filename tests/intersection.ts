/** A controllable IntersectionObserver for jsdom, which has none. */
interface FakeObserver {
  callback: IntersectionObserverCallback;
  options: IntersectionObserverInit | undefined;
  elements: Element[];
}

const observers: FakeObserver[] = [];

class FakeIntersectionObserver {
  private readonly record: FakeObserver;
  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.record = { callback, options, elements: [] };
    observers.push(this.record);
  }
  observe(el: Element) {
    this.record.elements.push(el);
  }
  unobserve() {}
  disconnect() {
    this.record.elements = [];
  }
  takeRecords() {
    return [];
  }
}

export function installFakeIntersectionObserver(): void {
  observers.length = 0;
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = FakeIntersectionObserver;
}

export const lastObserverOptions = () => observers[observers.length - 1].options!;

/** Report that `el` has scrolled near the viewport. */
export function intersect(el: Element): void {
  const owner = observers.find((o) => o.elements.includes(el));
  if (!owner) throw new Error('element is not being observed');
  owner.callback([{ target: el, isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
}
