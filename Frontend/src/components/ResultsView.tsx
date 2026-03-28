import { ExternalLink, PackageSearch, Star } from 'lucide-react';
import { useRecommendation } from '../context/RecommendationContext';

export default function ResultsView() {
  const { recommendations, summary } = useRecommendation();

  if (!recommendations?.length) {
    return null;
  }

  return (
    <div className="mt-2 overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/80">
      <div className="border-b border-white/8 px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/8 bg-white/[0.04] text-zinc-200">
            <PackageSearch size={20} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Recommended Products</h2>
            <p className="text-sm text-zinc-500">Shortlisted from your chat and preferences</p>
          </div>
        </div>
        {summary && <p className="mt-4 max-w-4xl text-sm leading-7 text-zinc-400">{summary}</p>}
      </div>

      <div className="space-y-6 px-6 py-6">
        {recommendations.map((category, catIdx) => (
          <section key={catIdx} className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-white">{category.category}</h3>
                <p className="mt-1 text-sm text-zinc-500">
                  {category.products.length} product{category.products.length === 1 ? '' : 's'} found
                </p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {category.products.map((product, prodIdx) => (
                <article
                  key={prodIdx}
                  className="rounded-[26px] border border-white/8 bg-[#17171d] p-5 transition hover:border-white/15 hover:bg-[#1b1b23]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h4 className="text-lg font-semibold leading-7 text-white">{product.title}</h4>
                      {product.explanation && (
                        <p className="mt-3 text-sm leading-7 text-zinc-400">{product.explanation}</p>
                      )}
                    </div>
                    {product.label && (
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-300">
                        {product.label}
                      </span>
                    )}
                  </div>

                  <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
                    {product.price && (
                      <span className="rounded-full bg-white px-3 py-1.5 font-semibold text-black">
                        {product.price}
                      </span>
                    )}
                    {product.source && <span className="text-zinc-500">{product.source}</span>}
                  </div>

                  {product.rating !== undefined && (
                    <div className="mt-4 flex items-center gap-3 text-sm text-zinc-400">
                      <div className="flex items-center">
                        {[...Array(5)].map((_, i) => (
                          <Star
                            key={i}
                            size={14}
                            className={
                              i < Math.round(product.rating!)
                                ? 'fill-amber-400 text-amber-400'
                                : 'text-zinc-700'
                            }
                          />
                        ))}
                      </div>
                      <span>{product.reviews ? `${product.reviews} reviews` : 'Recommended pick'}</span>
                    </div>
                  )}

                  <div className="mt-5">
                    <a
                      href={product.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/[0.08]"
                    >
                      View Product
                      <ExternalLink size={14} />
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
