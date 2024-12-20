const { Client, Events, GatewayIntentBits, Collection } = require('discord.js');
const { joinVoiceChannel, VoiceReceiver, EndBehaviorType, createAudioPlayer, NoSubscriberBehavior, createAudioResource, StreamType, AudioPlayerStatus, VoiceConnectionStatus, entersState } = require('@discordjs/voice');
const fs = require('node:fs');
const { connect } = require('node:http2');
const path = require('node:path');
const { Stream } = require('node:stream');
const WebSocket = require('ws');
const Prism = require('prism-media');
require('dotenv').config();

// クライアントを作成
const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
// コマンドを格納するCollectionを作成
client.commands = new Collection();
// VCを格納する変数を作成
let connectedVC = null;
let ws = null;
// Playerを作成
const player = createAudioPlayer({
	behaviors: {
		noSubscriber: NoSubscriberBehavior.Play,
	},
});
// 音声を再生していいか
let canPlay = true;
// 音声を再生しているか
let isPlaying = false;
// ポーズ中かどうか
let isPaused = false;
// 再生する音声ファイルのキュー
let playQueue = [];
// 再生中の音声ファイルのパス
let playingFile = '';

// 音声を再生する関数
function playAudio() {
    if (playQueue.length === 0) {
        console.log('再生する音声ファイルがありません。再生を終了します。');
        isPlaying = false;
        return;
    }
    if (connectedVC === null) {
        console.log('VCに接続していません。音声を再生できません。');
        isPlaying = false;
        return;
    }
    if (!canPlay) {
        console.log('canPlayフラグがfalseです。音声を再生できません。 at playAudio');
        isPlaying = false;
        return;
    }
    isPlaying = true;
    playingFile = playQueue.shift();
    console.log('再生する音声ファイル:', playingFile);
    const resource = createAudioResource(playingFile, {
        inputType: StreamType.Arbitrary,
    });
    player.play(resource);
}

// Playerの状態が変化したときの処理
player.on(AudioPlayerStatus.Idle, () => {
    console.log('PlayerがIdle状態になりました。');
    isPlaying = false;
    // 再生した音声ファイルを削除する
    fs.unlink(playingFile, (error) => {
        if (error) {
            console.error('音声ファイルの削除中にエラーが発生しました:', error);
        }
    });
    if (canPlay) {
        console.log('再生を続行します。');
        playAudio();
    } else {
        console.log('canPlayフラグがfalseです。再生を終了します。at Idle');
    }
});

player.on(AudioPlayerStatus.Paused, () => {
    isPlaying = false;
    canPlay = false;
    isPaused = true;
    console.log('PlayerがPause状態になりました。');
});

// WebSocket接続を確立する関数
function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('既に接続済みです');
        return;
    }
    ws = new WebSocket('ws://localhost:8765');
    ws.on('error', (error) => {
        console.error('WebSocket接続エラー:', error.message);
    });
    ws.on('open', () => {
        console.log('WebSocket接続が確立されました');
    });
    ws.on('message', (message) => {
        const strMessage = message.toString();
        console.log('メッセージを受け取りました:', strMessage);
        if (strMessage === 'ready') {
            console.log('Pythonプログラムが準備完了しました');
        }
        if (strMessage.endsWith('.wav') || strMessage.endsWith('.mp3')) {
            //console.log('Received audio file:', strMessage);
            if (isPlaying) {
                console.log('再生中です。再生キューに追加します。');
                playQueue.push(strMessage);
            } else {
                console.log('再生中ではありません。直ちに再生します。');
                playQueue = [strMessage];
                playAudio();
            }
        }
        if (strMessage === 'restart') {
            console.log('restartコマンドを受け取りました');
            canPlay = true; // 再生可能フラグをtrueにする
            isPlaying = true;
            if (isPaused) {
                isPaused = false;
                player.unpause(); // 一時停止を解除する
            } else {
                playAudio();
            }
        }
        if (strMessage === 'delete') {
            console.log('deleteコマンドを受け取りました');
            isPlaying = false;
            canPlay = true; // 再生可能フラグをtrueにする
            player.pause(); // 再生を一時停止する
            // 再生キューにある音声ファイルを削除する
            for (const audioFile of playQueue) {
                fs.unlink(audioFile, (error) => {
                    if (error) {
                        console.error('音声ファイルの削除中にエラーが発生しました:', error);
                    }
                });
            }
            playQueue = []; // 再生キューを空にする
        }
    });
    ws.on('close', () => {
        console.log('WebSocket接続が切断されました。5秒後に再接続を試みます...');
        setTimeout(connectWebSocket, 5000);
    });
}

// 起動時に少し遅延を入れて接続を試みる
setTimeout(connectWebSocket, 3000);

// ユーザーがVCに参加したときの処理
client.on(Events.VoiceStateUpdate, async (oldState, newState) => {
    try {
        if (newState.member.user.bot) return;  // ボットは無視
        if (oldState.channelId === newState.channelId) return;  // VC移動以外は無視
        if (oldState.channelId === null) {
            // VCに参加したとき
            console.log(`${newState.member.user.tag}がVCに参加しました。`);
            console.log('BotがVCに参加します。');
            try {
                connectedVC = joinVoiceChannel({
                    guildId: newState.guild.id,
                    channelId: newState.channelId,
                    adapterCreator: newState.guild.voiceAdapterCreator,
                });
            } catch (error) {
                console.error('VCへの参加中にエラーが発生しました:', error);
                return;
            }
            // PlayerをVCに接続
            connectedVC.subscribe(player);
            // 音声を取得する準備
            const receiver = connectedVC.receiver;
            // ユーザーが話し始めたとき
            receiver.speaking.on('start', userId => {
                canPlay = false; // 再生可能フラグをfalseにする
                player.pause(); // 再生を一時停止する
                console.log(`${userId}が話し始めました。`);
                // Pythonプログラムに通知
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send('speech_start');
                }
                // 録音する
                const audioStream = receiver.subscribe(userId, {
                    end: {
                        behavior: EndBehaviorType.AfterSilence,
                        duration: 100,
                    }
                });
                var file_name = './recorded/' + Date.now() + '.wav';
                var pcmBuffer = [];
                const opusDecoder = new Prism.opus.Decoder({
                    frameSize: 960,
                    channels: 2,
                    rate: 48000,
                });
                opusDecoder.on('data', (chunk) => {
                    pcmBuffer.push(chunk);
                });
                audioStream.pipe(opusDecoder);
                audioStream.on('end', () => {
                    console.log('音声の録音が終了しました。');
                    const pcmData = Buffer.concat(pcmBuffer);
                    const wavData = createWavFile(pcmData);
                    fs.writeFileSync(file_name, wavData);
                    // Pythonプログラムに通知
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send('speech_end');
                        ws.send(file_name);
                        canPlay = true; // 再生可能フラグをtrueにする
                    }
                });
            });
        } else if (newState.channelId === null) {
            if (connectedVC === null) return;  // BotがVCに参加していないときは無視
            // VCから退出したとき
            console.log(`${newState.member.user.tag}がVCから退出しました。`);
            console.log('BotがVCから退出します。');
            try {
                connectedVC.destroy();
            } catch (error) {
                console.error('VCから退出中にエラーが発生しました:', error);
            }
        }
    } catch (error) {
        console.error('VoiceStateUpdate イベントの処理中にエラーが発生しました:', error);
    }
});

// WAVファイルの作成
function createWavFile(buffer, sampleRate = 48000, numChannels = 2, bitDepth = 16) {
    const byteRate = (sampleRate * numChannels * bitDepth) / 8;
    const blockAlign = (numChannels * bitDepth) / 8;
    const dataSize = buffer.length;

    const header = Buffer.alloc(44);
    header.write('RIFF', 0); // RIFFヘッダー
    header.writeUInt32LE(36 + dataSize, 4); // チャンクサイズ (44 - 8 + dataSize)
    header.write('WAVE', 8); // フォーマット
    header.write('fmt ', 12); // 'fmt 'チャンク
    header.writeUInt32LE(16, 16); // fmtチャンクのサイズ（16バイト）
    header.writeUInt16LE(1, 20); // フォーマット (1 = PCM)
    header.writeUInt16LE(numChannels, 22); // チャンネル数
    header.writeUInt32LE(sampleRate, 24); // サンプリングレート
    header.writeUInt32LE(byteRate, 28); // バイトレート
    header.writeUInt16LE(blockAlign, 32); // ブロックサイズ
    header.writeUInt16LE(bitDepth, 34); // ビット深度
    header.write('data', 36); // dataチャンク
    header.writeUInt32LE(dataSize, 40); // dataチャンクのサイズ

    return Buffer.concat([header, buffer]);
}

// コマンドファイルを読み込む
const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

// コマンドを登録
for (const file of commandFiles) {
    try {
        const command = require(path.join(commandsPath, file));
        if ('data' in command && 'execute' in command) {
            client.commands.set(command.data.name, command);
        }
    } catch (error) {
        console.error(`コマンドファイル ${file} の読み込み中にエラーが発生しました:`, error);
    }
}

// コマンド実行処理
client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isChatInputCommand()) return;  // コマンド以外は無視
    const command = interaction.client.commands.get(interaction.commandName);
    if (!command) {
        await interaction.reply({ content: 'コマンドが見つかりません', ephemeral: true });
        return;
    }
    // コマンドの実行とエラーハンドリング
    try {
        await command.execute(interaction);
    } catch (error) {
        console.error(`コマンド ${interaction.commandName} の実行中にエラーが発生しました:`, error);
        await interaction.reply({ content: 'エラーが発生しました', ephemeral: true });
    }
});


// ボットが起動したときの処理
client.once(Events.ClientReady, readyClient => {
    console.log(`${readyClient.user.tag}でログインしました。`);
});

// ボットをログイン
console.log("起動しました。ログインします。");
client.login(process.env.DISCORD_TOKEN).catch(error => {
    console.error('ログイン中にエラーが発生しました:', error);
});