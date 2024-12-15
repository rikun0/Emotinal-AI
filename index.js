const { Client, Events, GatewayIntentBits, Collection } = require('discord.js');
const { joinVoiceChannel, VoiceReceiver, EndBehaviorType } = require('@discordjs/voice');
const fs = require('node:fs');
const { connect } = require('node:http2');
const path = require('node:path');
const { Stream } = require('node:stream');
require('dotenv').config();

// クライアントを作成
const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
// コマンドを格納するCollectionを作成
client.commands = new Collection();
// VCを格納する変数を作成
let connectedVC = null;

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
            // 音声を取得する準備
            const receiver = connectedVC.receiver;
            // ユーザーが話し始めたとき
            receiver.speaking.on('start', userId => {
                console.log(`${userId}が話し始めました。`);
                // 録音する
                const audioStream = receiver.subscribe(userId, {
                    end: {
                        behavior: EndBehaviorType.AfterSilence,
                        duration: 100,
                    }
                });
                var filename = './recorded/' + Date.now() + '.dat';
                var file = fs.createWriteStream(filename);
                Stream.pipeline(audioStream, file, (err) =>{
                    if(err){
                        console.error('録音中にエラーが発生しました:', err);
                    }else{
                        console.log(`${filename}に録音しました。`);
                    }
                });
            });
            // 話し終えたとき
            receiver.speaking.on('end', userId => {
                console.log(`${userId}が話し終えました。`);
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

// ボットが起動したときの処理
client.once(Events.ClientReady, readyClient => {
    console.log(`${readyClient.user.tag}でログインしました。`);
});

// ボットをログイン
console.log("起動しました。ログインします。");
client.login(process.env.DISCORD_TOKEN).catch(error => {
    console.error('ログイン中にエラーが発生しました:', error);
});