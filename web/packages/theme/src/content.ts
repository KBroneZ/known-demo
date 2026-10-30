import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { PostSchema } from '@demo/schema';

// Each site re-exports this from src/content.config.ts. Posts are Markdown files; the
// build fails if the frontmatter does not match PostSchema.
export const collections = {
  posts: defineCollection({
    loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
    schema: PostSchema,
  }),
};
