/**
 * Backend — aws-blocks/index.ts
 *
 * Real-time todo app with per-user isolation, optimistic locking, and secondary indexes.
 *
 * This file defines your API, auth, data model, and real-time channels.
 * The frontend imports these exports directly via `import { ... } from 'aws-blocks'`.
 *
 * ─── IMPORTANT ───────────────────────────────────────────────────────────────
 * Do NOT use local files, in-memory arrays, or local databases for persistence.
 * Use Building Blocks for cloud persistence and other common cloud abstractions.
 * They work locally with automatic mocks and deploy to AWS with zero configuration.
 *
 * For the full list of blocks and how to use them, see:
 *   node_modules/@aws-blocks/blocks/README.md
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { ApiNamespace, Scope, AuthBasic, DistributedTable, Realtime } from '@aws-blocks/blocks';
import { z } from 'zod';

const scope = new Scope('my-app');

// ─── Auth ────────────────────────────────────────────────────────────────────
const auth = new AuthBasic(scope, 'auth', {
  passwordPolicy: { minLength: 8 },
  crossDomain: process.env.BLOCKS_SANDBOX === 'true',
});
export const authApi = auth.createApi();

// ─── Data ────────────────────────────────────────────────────────────────────
const todoSchema = z.object({
  userId: z.string(),
  todoId: z.string(),
  title: z.string(),
  completed: z.boolean(),
  priority: z.number(),
  version: z.number(),
  createdAt: z.number(),
});

const todos = new DistributedTable(scope, 'todos', {
  schema: todoSchema,
  key: { partitionKey: 'userId', sortKey: 'todoId' },
  indexes: {
    byPriority: { partitionKey: 'userId', sortKey: 'priority' },
    byTitle: { partitionKey: 'userId', sortKey: 'title' },
  },
});

// ─── Realtime ────────────────────────────────────────────────────────────────
const rt = new Realtime(scope, 'live', {
  namespaces: {
    todos: Realtime.namespace(z.object({
      action: z.enum(['created', 'updated', 'deleted']),
      todoId: z.string(),
    })),
  },
});

// ─── API ─────────────────────────────────────────────────────────────────────
export const api = new ApiNamespace(scope, 'api', (context) => ({

  async subscribeTodos() {
    const user = await auth.requireAuth(context);
    return rt.getChannel('todos', user.username);
  },

  async createTodo(title: string, priority: number = 2) {
    const user = await auth.requireAuth(context);
    const todoId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const todo = {
      userId: user.username,
      todoId,
      title,
      completed: false,
      priority,
      version: 1,
      createdAt: Date.now(),
    };
    await todos.put(todo);
    await rt.publish('todos', user.username, { action: 'created' as const, todoId });
    return todo;
  },

  async listTodos(sortBy?: 'priority' | 'title') {
    const user = await auth.requireAuth(context);
    if (sortBy) {
      const index = sortBy === 'priority' ? 'byPriority' : 'byTitle';
      return await Array.fromAsync(
        todos.query({ index, where: { userId: { equals: user.username } } })
      );
    }
    return await Array.fromAsync(
      todos.query({ where: { userId: { equals: user.username } } })
    );
  },

  async toggleTodo(todoId: string) {
    const user = await auth.requireAuth(context);
    const todo = await todos.get({ userId: user.username, todoId });
    if (!todo) throw new Error('Todo not found');
    await todos.put(
      { ...todo, completed: !todo.completed, version: todo.version + 1 },
      { ifFieldEquals: { version: todo.version } },
    );
    await rt.publish('todos', user.username, { action: 'updated' as const, todoId });
    return { success: true };
  },

  async deleteTodo(todoId: string) {
    const user = await auth.requireAuth(context);
    await todos.delete({ userId: user.username, todoId });
    await rt.publish('todos', user.username, { action: 'deleted' as const, todoId });
    return { success: true };
  },
}));
