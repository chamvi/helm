/*
 * Copyright (c) 2026.
 * Author Peter Placzek (tada5hi)
 * For the full copyright and license information,
 * view the LICENSE file that was distributed with this source code.
 */
import { createApp, cron, defineAgent, http } from '@chamvi/app';
import { simulateReadableStream } from 'ai';
import { MockLanguageModelV4 } from 'ai/test';

const usage = {
    inputTokens: { total: 1, noCache: 1, cacheRead: undefined, cacheWrite: undefined },
    outputTokens: { total: 1, text: 1, reasoning: undefined },
};
const finishReason = { unified: 'stop', raw: undefined };
const model = new MockLanguageModelV4({
    doGenerate: async () => ({ content: [{ type: 'text', text: 'pong' }], finishReason, usage, warnings: [] }),
    doStream: async () => ({
        stream: simulateReadableStream({ chunks: [
            { type: 'stream-start', warnings: [] },
            { type: 'text-start', id: 't0' },
            { type: 'text-delta', id: 't0', delta: 'pong' },
            { type: 'text-end', id: 't0' },
            { type: 'finish', finishReason, usage },
        ] }),
    }),
});
export default createApp({ agents: [defineAgent({
    name: 'ping', model, instructions: 'Answer pong.',
    channels: [http.on(), cron.on('0 0 1 1 *')],
})] });
